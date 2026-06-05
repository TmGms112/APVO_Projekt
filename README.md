# APVO_Projekt

Full-stack audio library application with MongoDB-backed audio uploads, analysis, machine-learning playlists, playback, and next-song recommendations.

## Structure

- `frontend/` - Vite + React client.
- `backend/` - FastAPI API, MongoDB/GridFS storage, Redis cache helpers, audio-analysis worker, legacy MinIO object-storage compatibility, and ML endpoints.
- `docs/` - Project report material for describing the analytical workflow and results.

## Runtime Architecture

1. The React app uploads audio through `POST /songs/upload`.
2. FastAPI stores new uploaded files directly in MongoDB GridFS and stores song metadata in the `songs` collection.
3. Existing legacy records with `file_key` and `bucket` are also supported for playback/analysis through MinIO if the referenced files are available.
4. A background worker polls MongoDB for songs that are missing the new ML `features` field.
5. The worker reads audio bytes from GridFS or legacy MinIO object storage, calculates hashes, extracts metadata and audio features, and updates the song document.
6. The ML API builds model vectors from analyzed song data while excluding hash values, hash-derived duplicate flags, technical IDs and timestamps.
7. The ML API compares K-Means and Agglomerative Clustering on those vectors and stores the best model run.
8. The app displays songs, playback controls, model statistics, generated playlists, and next-song recommendations.

## Existing MongoDB Data

The default database name is `spotify` because the existing project data uses `spotify.songs`. New GridFS uploads also use this database.

The Compose stack includes MinIO again because old `spotify.songs` records use this shape:

```js
file_key: "...mp3"
bucket: "songs"
status: "uploaded"
```

That means MongoDB stores metadata, while MinIO stores the actual MP3 bytes. If MinIO is not running or its old volumes are missing, the app can list the songs but cannot play or analyze them.

If your MongoDB is not the Docker Compose Mongo service, set these environment variables before starting the backend:

```bash
MONGO_URL=mongodb://host.docker.internal:27017/spotify
MONGO_DB_NAME=spotify
```

For legacy documents with `file_key`, the matching MinIO files must be reachable. With the included Compose stack, backend and worker default to:

```bash
MINIO_ENDPOINT=minio1:9000
MINIO_ACCESS_KEY=minio
MINIO_SECRET_KEY=minio123
MINIO_BUCKET=songs
```

Do not run `docker compose down -v` unless you intentionally want to delete MongoDB and MinIO volumes.

`Legacy storage` in the UI means the song was uploaded by the old app version. MongoDB has a song document with a `file_key`, but the MP3 bytes are stored in MinIO, not inside the document itself.

You can inspect the current backend view of storage/status and a sample of MinIO object availability with:

```text
http://localhost:8000/songs/storage-summary?sample=100
```

You can inspect one specific song object with:

```text
http://localhost:8000/songs/<song_id>/storage-check
```

Old `status: "processed"` songs from the first app version may have fields like `audio_artist`, `audio_bitrate`, `duration_seconds`, and `hash`, but still lack the new ML `features` and `feature_vector` fields. The current worker intentionally reprocesses any song that has reachable audio storage and is missing `features`, even if its old status is already `processed`.

## Machine Learning Functionality

The app uses content-based recommendation. It extracts tempo, energy, spectral, MFCC and chroma features from each uploaded song and combines them with other analyzed song metadata and file attributes. Hash values are kept for duplicate detection, but they are not used by the models.

It evaluates two clustering models:

- K-Means Clustering
- Agglomerative Clustering

The selected model is chosen by the best silhouette score, with Davies-Bouldin score used as a tie-breaker. The selected clustering result is used to create automatic playlists. Cosine similarity over standardized non-hash song vectors recommends the next song.

The Docker images install `ffmpeg` and `libsndfile1` so Librosa can decode common audio formats during worker analysis.

## Local Development

Backend stack:

```bash
cd backend
docker compose up --build
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend proxies `/api` to the backend on `http://127.0.0.1:8000` during development.

## Key Endpoints

- `POST /songs/upload` - upload audio to MongoDB/GridFS.
- `GET /songs/?limit=1000` - list songs and analysis status.
- `GET /songs/storage-summary` - count GridFS, legacy and missing storage records.
- `GET /songs/{song_id}/storage-check` - check if one song's referenced audio object exists.
- `GET /songs/{song_id}/stream` - stream audio for playback.
- `POST /ml/train` - evaluate models and store the selected model run.
- `GET /ml/stats` - dataset statistics and chart-ready distributions.
- `GET /ml/playlists` - generated playlists from the selected model.
- `GET /ml/recommendations/{song_id}` - next-song recommendations.
