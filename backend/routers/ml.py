from collections import defaultdict
from datetime import datetime
from math import sqrt
from numbers import Number

import numpy as np
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from database import db

router = APIRouter(prefix="/ml", tags=["machine-learning"])

HASH_FIELDS = {"hash", "md5_hash"}
TECHNICAL_FIELDS = {
    "_id",
    "id",
    "file_id",
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

NUMERIC_TOP_LEVEL_FIELDS = {
    "file_size",
    "duration",
    "duration_seconds",
    "year",
    "audio_year",
    "audio_bitrate",
    "audio_samplerate",
    "audio_channels",
}
CATEGORICAL_TOP_LEVEL_FIELDS = {
    "title",
    "artist",
    "album",
    "genre",
    "filename",
    "content_type",
    "audio_title",
    "audio_artist",
    "audio_album",
    "audio_genre",
}


async def _analyzed_songs():
    songs = []
    async for song in db.songs.find({"analysis_status": "done"}):
        if _model_fields(song):
            songs.append(song)
    return songs


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
    return text if text else None


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

        if key in NUMERIC_TOP_LEVEL_FIELDS:
            number = _as_float(value)
            if number is not None:
                numeric[key] = number
            continue

        if key in CATEGORICAL_TOP_LEVEL_FIELDS:
            category = _clean_category(value)
            if category is not None:
                categorical[key] = category

    return {"numeric": numeric, "categorical": categorical}


def _build_schema(songs):
    numeric_fields = set()
    categorical_values = defaultdict(set)

    for song in songs:
        fields = _model_fields(song)
        numeric_fields.update(fields["numeric"].keys())
        for key, value in fields["categorical"].items():
            categorical_values[key].add(value)

    categorical_fields = {
        key: sorted(values)
        for key, values in sorted(categorical_values.items())
        if values
    }

    return {
        "numeric_fields": sorted(numeric_fields),
        "categorical_fields": categorical_fields,
        "excluded_fields": sorted(EXCLUDED_MODEL_FIELDS),
        "description": "Uses analyzed song audio features, metadata and file attributes; excludes hashes, hash-derived duplicate flags, technical IDs and timestamps.",
    }


def _vectorize_song(song, schema):
    fields = _model_fields(song)
    vector = []

    for key in schema["numeric_fields"]:
        vector.append(float(fields["numeric"].get(key, 0.0)))

    for key, categories in schema["categorical_fields"].items():
        value = fields["categorical"].get(key)
        vector.extend(1.0 if value == category else 0.0 for category in categories)

    return vector


def _matrix(songs, schema=None):
    schema = schema or _build_schema(songs)
    matrix = np.array([_vectorize_song(song, schema) for song in songs], dtype=float)
    if matrix.size == 0 or matrix.shape[1] == 0:
        raise HTTPException(
            status_code=400,
            detail="Analyzed songs do not contain enough usable non-hash fields for ML training.",
        )
    return matrix, schema


def _cluster_count(sample_count):
    if sample_count < 3:
        raise HTTPException(
            status_code=400,
            detail="At least 3 analyzed songs are required to compare clustering models.",
        )
    return max(2, min(5, sample_count - 1, round(sqrt(sample_count))))


def _metrics(x_scaled, labels):
    unique = set(int(label) for label in labels)
    if len(unique) < 2 or len(unique) >= len(labels):
        return {
            "silhouette_score": None,
            "davies_bouldin_score": None,
            "calinski_harabasz_score": None,
        }

    return {
        "silhouette_score": float(silhouette_score(x_scaled, labels)),
        "davies_bouldin_score": float(davies_bouldin_score(x_scaled, labels)),
        "calinski_harabasz_score": float(calinski_harabasz_score(x_scaled, labels)),
    }


def _pick_best(results):
    def score(result):
        silhouette = result["metrics"].get("silhouette_score")
        davies = result["metrics"].get("davies_bouldin_score")
        return (
            silhouette if silhouette is not None else -999.0,
            -(davies if davies is not None else 999.0),
        )

    return max(results, key=score)


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


@router.post("/train")
async def train_models():
    songs = await _analyzed_songs()
    x, schema = _matrix(songs)
    k = _cluster_count(len(songs))

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    kmeans_labels = kmeans.fit_predict(x_scaled)

    agglomerative = AgglomerativeClustering(n_clusters=k)
    agglomerative_labels = agglomerative.fit_predict(x_scaled)

    results = [
        {
            "model_name": "K-Means",
            "description": "Partitions songs into k groups by minimizing distance to cluster centers.",
            "cluster_count": k,
            "labels": [int(label) for label in kmeans_labels],
            "metrics": {
                **_metrics(x_scaled, kmeans_labels),
                "inertia": float(kmeans.inertia_),
            },
        },
        {
            "model_name": "Agglomerative Clustering",
            "description": "Builds song groups bottom-up by merging the most similar songs and clusters.",
            "cluster_count": k,
            "labels": [int(label) for label in agglomerative_labels],
            "metrics": _metrics(x_scaled, agglomerative_labels),
        },
    ]

    best = _pick_best(results)
    best_labels = best["labels"]

    pca_points = []
    pca = PCA(n_components=2, random_state=42)
    reduced = pca.fit_transform(x_scaled)
    for song, point, label in zip(songs, reduced, best_labels):
        pca_points.append(
            {
                "song_id": str(song["_id"]),
                "title": song.get("title"),
                "artist": song.get("artist"),
                "cluster": int(label),
                "x": float(point[0]),
                "y": float(point[1]),
            }
        )

    cluster_summary = _cluster_summary(songs, best_labels)
    run_doc = {
        "trained_at": datetime.utcnow(),
        "song_count": len(songs),
        "feature_schema": schema,
        "feature_count": int(x.shape[1]),
        "cluster_count": k,
        "models_tested": results,
        "selected_model": {
            "model_name": best["model_name"],
            "selection_reason": "Selected by highest silhouette score, using Davies-Bouldin as tie-breaker.",
            "metrics": best["metrics"],
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

    featured = [song for song in all_songs if song.get("analysis_status") == "done"]
    statuses = defaultdict(int)
    for song in all_songs:
        statuses[song.get("analysis_status", "unknown")] += 1

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
        summary = summaries.get(cluster, {"cluster": cluster, "song_count": len(cluster_songs)})
        result.append(
            {
                "cluster": cluster,
                "name": f"{_playlist_name(summary)} {cluster + 1}",
                "description": (
                    f"Generated by {latest['selected_model']['model_name']} from analyzed song data "
                    "excluding hashes and technical identifiers."
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
    x_scaled = StandardScaler().fit_transform(x)
    similarities = cosine_similarity([x_scaled[target_index]], x_scaled)[0]
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
