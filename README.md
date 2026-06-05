# APVO_Projekt

Full-stack audio library application with MongoDB-backed audio uploads, analysis, machine-learning playlists, playback, and next-song recommendations.

## Structure

- `frontend/` - Vite + React client.
- `backend/` - FastAPI API, MongoDB/GridFS storage, Redis cache helpers, audio-analysis worker, legacy object-storage compatibility, and ML endpoints.
- `docs/` - Project report material for describing the analytical workflow and results.

## Runtime Architecture

1. The React app uploads audio through `POST /songs/upload`.
2. FastAPI stores new uploaded files directly in MongoDB GridFS and stores song metadata in the `songs` collection.
3. Existing legacy records with `file_key` and `bucket` are also supported for playback/analysis if the referenced object-storage files are available.
4. A background worker polls MongoDB for songs that need analysis.
5. The worker reads audio bytes from GridFS or legacy object storage, calculates hashes, extracts metadata and audio features, and updates the song document.
6. The ML API builds model vectors from analyzed song data while excluding hash values, hash-derived duplicate flags, technical IDs and timestamps.
7. The ML API compares K-Means and Agglomerative Clustering on those vectors and stores the best model run.
8. The app displays songs, playback controls, model statistics, generated playlists, and next-song recommendations.

## Existing MongoDB Data

The default database name is `spotify` because the existing project data uses `spotify.songs`. New GridFS uploads also use this database.

If your MongoDB is not the Docker Compose Mongo service, set these environment variables before starting the backend:

```bash
MONGO_URL=mongodb://host.docker.internal:27017/spotify
MONGO_DB_NAME=spotify
```

For legacy documents with `file_key`, playback and worker analysis also need the matching object storage files. Configure these if your old songs are stored in MinIO:

```bash
MINIO_ENDPOINT=host.docker.internal:9000
MINIO_ACCESS_KEY=minio
MINIO_SECRET_KEY=minio123
MINIO_BUCKET=songs
```

`Legacy storage` in the UI means the song was uploaded by the old app version. MongoDB has a song document with a `file_key`, but the MP3 bytes are not stored in that document. The app must fetch the audio from the old object storage bucket, usually MinIO. If the MongoDB documents exist but the referenced audio files do not exist in GridFS or MinIO, the app can list the songs but cannot play or analyze them.

You can inspect the current backend view of storage/status with:

```text
http://localhost:8000/songs/storage-summary
```

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
- `GET /songs/{song_id}/stream` - stream audio for playback.
- `POST /ml/train` - evaluate models and store the selected model run.
- `GET /ml/stats` - dataset statistics and chart-ready distributions.
- `GET /ml/playlists` - generated playlists from the selected model.
- `GET /ml/recommendations/{song_id}` - next-song recommendations.
