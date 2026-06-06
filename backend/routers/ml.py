from collections import Counter, defaultdict
from datetime import datetime
from math import sqrt
from numbers import Number

import numpy as np
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.feature_selection import VarianceThreshold
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import RobustScaler, StandardScaler

from database import db

router = APIRouter(prefix="/ml", tags=["machine-learning"])

HASH_FIELDS = {"hash", "md5_hash"}
TECHNICAL_FIELDS = {
    "_id",
    "id",
    "file_id",
    "file_key",
    "bucket",
    "storage_kind",
    "can_stream",
    "duplicate_of",
    "feature_vector",
    "feature_names",
    "analysis_status",
    "uploaded_at",
    "processed_at",
    "processing_started_at",
    "error",
    "ml_cluster",
    "ml_model",
    "ml_model_run_id",
    "ml_pca",
}
HASH_DERIVED_FIELDS = {"is_duplicate", "duplicate_of"}
EXCLUDED_MODEL_FIELDS = HASH_FIELDS | TECHNICAL_FIELDS | HASH_DERIVED_FIELDS
LOW_CARDINALITY_LIMIT = 12
MAX_CLUSTER_CANDIDATES = 12
TARGET_MAX_CLUSTER_FRACTION = 0.45


def _serialize_value(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def _serialize_song(song):
    return {
        key if key != "_id" else "id": _serialize_value(value)
        for key, value in song.items()
        if key not in {"feature_vector"}
    }


def _as_float(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Number):
        value = float(value)
        return value if np.isfinite(value) else None
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
            return parsed if np.isfinite(parsed) else None
        except ValueError:
            return None
    return None


def _clean_category(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in {"unknown", "unknown artist", "none", "null"}:
        return None
    return text


def _model_fields(song):
    numeric = {}
    categorical = {}

    features = song.get("features") or {}
    for key, value in features.items():
        number = _as_float(value)
        if number is not None:
            numeric[f"features.{key}"] = number

    for key, value in song.items():
        if key in EXCLUDED_MODEL_FIELDS or key in {"features"}:
            continue

        number = _as_float(value)
        if number is not None:
            numeric[key] = number
            continue

        if isinstance(value, bool):
            numeric[key] = 1.0 if value else 0.0
            continue

        if isinstance(value, (str, int, float)):
            category = _clean_category(value)
            if category is not None:
                categorical[key] = category

    return {"numeric": numeric, "categorical": categorical}


def _build_schema(songs):
    numeric_fields = set()
    categorical_counts = defaultdict(Counter)

    for song in songs:
        fields = _model_fields(song)
        numeric_fields.update(fields["numeric"].keys())
        for key, value in fields["categorical"].items():
            categorical_counts[key][value] += 1

    categorical_fields = {}
    for key, counts in sorted(categorical_counts.items()):
        values = sorted(counts)
        use_one_hot = len(values) <= LOW_CARDINALITY_LIMIT
        categorical_fields[key] = {
            "counts": dict(counts),
            "categories": values if use_one_hot else [],
            "encoding": "one_hot_plus_text_stats" if use_one_hot else "text_stats",
        }

    vector_names = []
    vector_names.extend(sorted(numeric_fields))
    for key, info in categorical_fields.items():
        vector_names.extend(
            [
                f"{key}.known",
                f"{key}.length",
                f"{key}.token_count",
                f"{key}.value_frequency",
            ]
        )
        vector_names.extend(f"{key}={category}" for category in info["categories"])

    return {
        "numeric_fields": sorted(numeric_fields),
        "categorical_fields": categorical_fields,
        "vector_names": vector_names,
        "excluded_fields": sorted(EXCLUDED_MODEL_FIELDS),
        "description": (
            "Uses analyzed audio features plus available non-hash metadata and file attributes. "
            "High-cardinality text fields are encoded as compact text/frequency features instead of sparse one-hot columns; "
            "hashes, hash-derived duplicate flags, storage references, technical IDs and timestamps are excluded."
        ),
    }


def _schema_needs_rebuild(schema):
    if not schema or "vector_names" not in schema:
        return True
    for info in (schema.get("categorical_fields") or {}).values():
        if not isinstance(info, dict) or "counts" not in info:
            return True
    return False


def _vectorize_song(song, schema):
    fields = _model_fields(song)
    vector = []

    for key in schema["numeric_fields"]:
        vector.append(float(fields["numeric"].get(key, 0.0)))

    for key, info in schema["categorical_fields"].items():
        value = fields["categorical"].get(key)
        counts = info.get("counts") or {}
        if value:
            token_count = len(value.split())
            frequency = counts.get(value, 0) / max(1, sum(counts.values()))
            vector.extend([1.0, float(len(value)), float(token_count), float(frequency)])
        else:
            vector.extend([0.0, 0.0, 0.0, 0.0])
        vector.extend(1.0 if value == category else 0.0 for category in info.get("categories", []))

    return vector


def _matrix(songs, schema=None):
    if _schema_needs_rebuild(schema):
        schema = _build_schema(songs)
    matrix = np.array([_vectorize_song(song, schema) for song in songs], dtype=float)
    if matrix.size == 0 or matrix.shape[1] == 0:
        raise HTTPException(
            status_code=400,
            detail="Analyzed songs do not contain enough usable non-hash fields for ML training.",
        )
    return matrix, schema


def _analyzed_query():
    return {"$or": [{"analysis_status": "done"}, {"status": "processed"}]}


async def _analyzed_songs():
    songs = []
    async for song in db.songs.find(_analyzed_query()):
        if _model_fields(song):
            songs.append(song)
    return songs


def _minimum_playlist_count(sample_count):
    if sample_count < 10:
        return 2
    if sample_count < 40:
        return 3
    if sample_count < 120:
        return 4
    return 5


def _candidate_cluster_counts(sample_count):
    if sample_count < 3:
        raise HTTPException(
            status_code=400,
            detail="At least 3 analyzed songs are required to compare clustering models.",
        )
    minimum = min(sample_count - 1, _minimum_playlist_count(sample_count))
    upper = min(
        sample_count - 1,
        max(minimum, round(sqrt(sample_count) * 1.7)),
        MAX_CLUSTER_CANDIDATES,
    )
    return list(range(minimum, upper + 1))


def _feature_weight(name):
    if name.startswith("features."):
        return 1.8
    if name in {"duration", "duration_seconds", "file_size", "audio_bitrate", "audio_samplerate"}:
        return 1.1
    if name.endswith((".known", ".length", ".token_count", ".value_frequency")):
        return 0.65
    return 0.85


def _prepare_feature_space(x, schema):
    scaler = RobustScaler()
    x_scaled = scaler.fit_transform(x)

    weights = np.array([_feature_weight(name) for name in schema.get("vector_names", [])], dtype=float)
    if weights.size == x_scaled.shape[1]:
        x_scaled = x_scaled * weights

    if x_scaled.shape[1] > 1:
        selector = VarianceThreshold(threshold=1e-8)
        try:
            x_scaled = selector.fit_transform(x_scaled)
        except ValueError:
            pass

    max_components = min(12, x_scaled.shape[0] - 1, x_scaled.shape[1])
    preprocessing = {
        "scaler": "RobustScaler",
        "feature_weighting": "Acoustic analysis features weighted higher than noisy text metadata.",
        "variance_threshold": 1e-8,
        "pca_components": None,
        "pca_explained_variance_ratio": None,
    }

    if max_components >= 2 and x_scaled.shape[1] > max_components:
        pca = PCA(n_components=max_components, random_state=42)
        x_model = pca.fit_transform(x_scaled)
        preprocessing["pca_components"] = int(max_components)
        preprocessing["pca_explained_variance_ratio"] = round(float(np.sum(pca.explained_variance_ratio_)), 4)
    else:
        x_model = x_scaled

    return StandardScaler().fit_transform(x_model), preprocessing


def _cluster_quality(labels):
    counts = np.array(list(Counter(int(label) for label in labels).values()), dtype=float)
    total = float(np.sum(counts))
    proportions = counts / total
    entropy = -float(np.sum(proportions * np.log(proportions)))
    normalized_entropy = entropy / float(np.log(len(counts))) if len(counts) > 1 else 0.0
    max_fraction = float(np.max(proportions))
    imbalance_penalty = max(0.0, max_fraction - TARGET_MAX_CLUSTER_FRACTION)

    return {
        "cluster_count": int(len(counts)),
        "max_cluster_size": int(np.max(counts)),
        "min_cluster_size": int(np.min(counts)),
        "max_cluster_fraction": max_fraction,
        "min_cluster_fraction": float(np.min(proportions)),
        "normalized_entropy": normalized_entropy,
        "imbalance_penalty": imbalance_penalty,
    }


def _metrics(x_model, labels):
    unique = set(int(label) for label in labels)
    quality = _cluster_quality(labels)
    if len(unique) < 2 or len(unique) >= len(labels):
        return {
            "silhouette_score": None,
            "davies_bouldin_score": None,
            "calinski_harabasz_score": None,
            "playlist_balance_score": quality["normalized_entropy"],
            "max_cluster_fraction": quality["max_cluster_fraction"],
        }

    return {
        "silhouette_score": float(silhouette_score(x_model, labels)),
        "davies_bouldin_score": float(davies_bouldin_score(x_model, labels)),
        "calinski_harabasz_score": float(calinski_harabasz_score(x_model, labels)),
        "playlist_balance_score": quality["normalized_entropy"],
        "max_cluster_fraction": quality["max_cluster_fraction"],
    }


def _candidate_score(result):
    metrics = result["metrics"]
    quality = result.get("playlist_quality") or {}
    silhouette = metrics.get("silhouette_score")
    davies = metrics.get("davies_bouldin_score")
    calinski = metrics.get("calinski_harabasz_score")
    entropy = quality.get("normalized_entropy", metrics.get("playlist_balance_score") or 0.0)
    imbalance_penalty = quality.get("imbalance_penalty", 0.0)
    cluster_count = result.get("cluster_count", 0)

    playlist_usefulness_score = (
        (silhouette if silhouette is not None else -1.0)
        + (0.45 * entropy)
        - (0.9 * imbalance_penalty)
        + (0.015 * min(cluster_count, 8))
    )

    return (
        playlist_usefulness_score,
        silhouette if silhouette is not None else -999.0,
        -(davies if davies is not None else 999.0),
        calinski if calinski is not None else -999.0,
    )


def _best_result(results):
    if not results:
        raise HTTPException(status_code=400, detail="No valid clustering result could be produced.")
    return max(results, key=_candidate_score)


def _fit_kmeans(x_model, cluster_counts):
    candidates = []
    for k in cluster_counts:
        model = KMeans(n_clusters=k, random_state=42, n_init=30)
        labels = model.fit_predict(x_model)
        quality = _cluster_quality(labels)
        candidates.append(
            {
                "model_name": "K-Means",
                "description": "Partitions songs around centroids after denoising and playlist-balance-aware cluster search.",
                "cluster_count": k,
                "labels": [int(label) for label in labels],
                "playlist_quality": quality,
                "metrics": {**_metrics(x_model, labels), "inertia": float(model.inertia_)},
            }
        )
    return _best_result(candidates)


def _fit_gaussian_mixture(x_model, cluster_counts):
    candidates = []
    for covariance_type in ["full", "diag"]:
        for k in cluster_counts:
            model = GaussianMixture(
                n_components=k,
                covariance_type=covariance_type,
                random_state=42,
                n_init=5,
                reg_covar=1e-5,
            )
            try:
                labels = model.fit_predict(x_model)
                metrics = _metrics(x_model, labels)
                bic = float(model.bic(x_model))
                aic = float(model.aic(x_model))
            except Exception:
                continue
            quality = _cluster_quality(labels)
            candidates.append(
                {
                    "model_name": "Gaussian Mixture",
                    "description": "Creates probabilistic song groups while avoiding one oversized playlist.",
                    "cluster_count": k,
                    "labels": [int(label) for label in labels],
                    "playlist_quality": quality,
                    "metrics": {
                        **metrics,
                        "bic": bic,
                        "aic": aic,
                        "covariance_type": covariance_type,
                    },
                }
            )
    return _best_result(candidates)


def _pick_best(results):
    return _best_result(results)


def _cluster_summary(songs, labels):
    grouped = defaultdict(list)
    for song, label in zip(songs, labels):
        grouped[int(label)].append(song)

    summaries = []
    for cluster, cluster_songs in sorted(grouped.items()):
        tempos = [song.get("features", {}).get("tempo") for song in cluster_songs]
        energies = [song.get("features", {}).get("rms_mean") for song in cluster_songs]
        durations = [song.get("duration_seconds") or song.get("duration") for song in cluster_songs]
        summaries.append(
            {
                "cluster": cluster,
                "song_count": len(cluster_songs),
                "average_tempo": _average(tempos),
                "average_energy": _average(energies),
                "average_duration_seconds": _average(durations),
            }
        )
    return summaries


def _average(values):
    clean = [float(value) for value in values if value is not None]
    return round(sum(clean) / len(clean), 3) if clean else None


def _histogram(values, bins=6):
    clean = np.array([float(value) for value in values if value is not None], dtype=float)
    if clean.size == 0:
        return []
    counts, edges = np.histogram(clean, bins=min(bins, max(1, clean.size)))
    return [
        {
            "min": round(float(edges[index]), 2),
            "max": round(float(edges[index + 1]), 2),
            "count": int(counts[index]),
        }
        for index in range(len(counts))
    ]


def _playlist_name(summary):
    tempo = summary.get("average_tempo") or 0
    energy = summary.get("average_energy") or 0
    if tempo >= 125 and energy >= 0.08:
        return "High Energy Mix"
    if tempo < 95:
        return "Chill Playlist"
    if energy >= 0.08:
        return "Upbeat Playlist"
    return "Balanced Playlist"


def _pca_points(songs, x_model, labels):
    if x_model.shape[1] >= 2:
        reduced = PCA(n_components=2, random_state=42).fit_transform(x_model)
    else:
        reduced = np.column_stack([x_model[:, 0], np.zeros(x_model.shape[0])])

    return [
        {
            "song_id": str(song["_id"]),
            "title": song.get("title"),
            "artist": song.get("artist"),
            "cluster": int(label),
            "x": float(point[0]),
            "y": float(point[1]),
        }
        for song, point, label in zip(songs, reduced, labels)
    ]


@router.post("/train")
async def train_models():
    songs = await _analyzed_songs()
    x, schema = _matrix(songs)
    x_model, preprocessing = _prepare_feature_space(x, schema)
    cluster_counts = _candidate_cluster_counts(len(songs))

    results = [
        _fit_kmeans(x_model, cluster_counts),
        _fit_gaussian_mixture(x_model, cluster_counts),
    ]

    best = _pick_best(results)
    best_labels = best["labels"]
    pca_points = _pca_points(songs, x_model, best_labels)
    cluster_summary = _cluster_summary(songs, best_labels)

    run_doc = {
        "trained_at": datetime.utcnow(),
        "song_count": len(songs),
        "feature_schema": schema,
        "feature_count": int(x.shape[1]),
        "model_feature_count": int(x_model.shape[1]),
        "candidate_cluster_counts": cluster_counts,
        "cluster_count": best["cluster_count"],
        "preprocessing": preprocessing,
        "playlist_quality": best.get("playlist_quality"),
        "models_tested": results,
        "selected_model": {
            "model_name": best["model_name"],
            "selection_reason": (
                "Selected by a playlist-usefulness score that combines silhouette quality with cluster balance; "
                "Davies-Bouldin and Calinski-Harabasz are retained for model reporting."
            ),
            "cluster_count": best["cluster_count"],
            "metrics": best["metrics"],
            "playlist_quality": best.get("playlist_quality"),
        },
        "cluster_summary": cluster_summary,
        "pca_points": pca_points,
    }

    result = await db.ml_model_runs.insert_one(run_doc)
    run_id = str(result.inserted_id)

    for song, label, point in zip(songs, best_labels, pca_points):
        await db.songs.update_one(
            {"_id": song["_id"]},
            {
                "$set": {
                    "ml_cluster": int(label),
                    "ml_model": best["model_name"],
                    "ml_model_run_id": run_id,
                    "ml_pca": {"x": point["x"], "y": point["y"]},
                }
            },
        )

    return await latest_model_run()


@router.get("/model-runs/latest")
async def latest_model_run():
    run = await db.ml_model_runs.find_one(sort=[("trained_at", -1)])
    if not run:
        return None
    return _serialize_song(run)


@router.get("/stats")
async def stats():
    all_songs = []
    async for song in db.songs.find({}):
        all_songs.append(song)

    featured = [
        song
        for song in all_songs
        if song.get("analysis_status") == "done" or song.get("status") == "processed"
    ]
    statuses = defaultdict(int)
    for song in all_songs:
        statuses[song.get("analysis_status") or song.get("status") or "unknown"] += 1

    tempos = [song.get("features", {}).get("tempo") for song in featured]
    energies = [song.get("features", {}).get("rms_mean") for song in featured]
    durations = [song.get("duration_seconds") or song.get("duration") for song in featured]

    latest = await latest_model_run()
    cluster_sizes = []
    if latest:
        cluster_sizes = latest.get("cluster_summary", [])

    return {
        "song_count": len(all_songs),
        "analyzed_song_count": len(featured),
        "analysis_status_counts": dict(statuses),
        "duplicate_count": sum(1 for song in all_songs if song.get("is_duplicate")),
        "average_tempo": _average(tempos),
        "average_energy": _average(energies),
        "average_duration_seconds": _average(durations),
        "total_duration_seconds": round(sum(float(value) for value in durations if value is not None), 2),
        "tempo_histogram": _histogram(tempos),
        "energy_histogram": _histogram(energies),
        "duration_histogram": _histogram(durations),
        "cluster_sizes": cluster_sizes,
        "latest_model_run": latest,
    }


@router.get("/playlists")
async def playlists():
    latest = await latest_model_run()
    if not latest:
        return {"message": "Train models before generating playlists.", "playlists": []}

    songs = []
    async for song in db.songs.find({"ml_model_run_id": latest["id"]}):
        songs.append(song)

    grouped = defaultdict(list)
    for song in songs:
        grouped[int(song.get("ml_cluster", -1))].append(song)

    summaries = {item["cluster"]: item for item in latest.get("cluster_summary", [])}
    result = []
    for cluster, cluster_songs in sorted(grouped.items()):
        cluster_songs.sort(key=lambda item: ((item.get("artist") or ""), (item.get("title") or "")))
        summary = summaries.get(cluster, {"cluster": cluster, "song_count": len(cluster_songs)})
        result.append(
            {
                "cluster": cluster,
                "name": f"{_playlist_name(summary)} {cluster + 1}",
                "description": (
                    f"Generated by {latest['selected_model']['model_name']} from analyzed song data "
                    "excluding hashes, storage references and technical identifiers."
                ),
                "song_count": len(cluster_songs),
                "average_tempo": summary.get("average_tempo"),
                "average_energy": summary.get("average_energy"),
                "songs": [_serialize_song(song) for song in cluster_songs],
            }
        )

    return {"model_run_id": latest["id"], "selected_model": latest["selected_model"], "playlists": result}


@router.get("/recommendations/{song_id}")
async def recommendations(song_id: str, limit: int = Query(5, ge=1, le=20)):
    if not ObjectId.is_valid(song_id):
        raise HTTPException(status_code=400, detail="Invalid song id")

    songs = await _analyzed_songs()
    target_index = next((index for index, song in enumerate(songs) if str(song["_id"]) == song_id), None)
    if target_index is None:
        raise HTTPException(status_code=404, detail="Song has no analyzed ML fields yet")
    if len(songs) < 2:
        return {"song_id": song_id, "recommendations": []}

    latest = await latest_model_run()
    schema = latest.get("feature_schema") if latest else None
    x, schema = _matrix(songs, schema=schema)
    x_model, _ = _prepare_feature_space(x, schema)
    similarities = cosine_similarity([x_model[target_index]], x_model)[0]
    target = songs[target_index]

    ranked = []
    for index, song in enumerate(songs):
        if index == target_index:
            continue
        same_cluster = target.get("ml_cluster") is not None and target.get("ml_cluster") == song.get("ml_cluster")
        tempo_gap = abs(
            float(target.get("features", {}).get("tempo") or 0)
            - float(song.get("features", {}).get("tempo") or 0)
        )
        ranked.append(
            {
                "song": _serialize_song(song),
                "similarity": round(float(similarities[index]), 4),
                "same_cluster": same_cluster,
                "reason": "same playlist cluster" if same_cluster else f"closest non-hash song profile, tempo gap {round(tempo_gap, 1)} BPM",
            }
        )

    ranked.sort(key=lambda item: item["similarity"], reverse=True)
    return {
        "song": _serialize_song(target),
        "feature_schema": schema,
        "recommendations": ranked[:limit],
    }
