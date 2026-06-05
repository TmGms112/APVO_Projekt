# APVO_Projekt

Full-stack audio library application with MongoDB-backed audio uploads, analysis, machine-learning playlists, and next-song recommendations.

## Structure

- `frontend/` - Vite + React client.
- `backend/` - FastAPI API, MongoDB/GridFS storage, Redis cache helpers, audio-analysis worker, and ML endpoints.
- `docs/` - Project report material for describing the analytical workflow and results.

## Runtime Architecture

1. The React app uploads audio through `POST /songs/upload`.
2. FastAPI stores the uploaded file directly in MongoDB GridFS and stores song metadata in the `songs` collection.
3. A background worker polls MongoDB for songs with `analysis_status: pending`.
4. The worker reads the audio bytes from GridFS, calculates hashes, extracts audio metadata and audio features, and updates the song document.
5. The ML API builds model vectors from analyzed song data while excluding hash values, hash-derived duplicate flags, technical IDs and timestamps.
6. The ML API compares K-Means and Agglomerative Clustering on those vectors and stores the best model run.
7. The app displays model statistics, generated playlists, and next-song recommendations from the user's uploaded songs.

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
- `GET /songs/` - list songs and analysis status.
- `POST /ml/train` - evaluate models and store the selected model run.
- `GET /ml/stats` - dataset statistics and chart-ready distributions.
- `GET /ml/playlists` - generated playlists from the selected model.
- `GET /ml/recommendations/{song_id}` - next-song recommendations.
