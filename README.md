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
5. The ML API compares K-Means and Agglomerative Clustering on extracted features and stores the best model run.
6. The app displays model statistics, generated playlists, and next-song recommendations from the user's uploaded songs.

## Machine Learning Functionality

The app uses content-based recommendation. It extracts tempo, energy, spectral, MFCC and chroma features from each uploaded song. It evaluates two clustering models:

- K-Means Clustering
- Agglomerative Clustering

The selected model is chosen by the best silhouette score, with Davies-Bouldin score used as a tie-breaker. The selected clustering result is used to create automatic playlists. Cosine similarity over standardized audio feature vectors recommends the next song.

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
