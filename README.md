# APVO_Projekt

Full-stack audio library application.

## Structure

- `frontend/` - Vite + React client.
- `backend/` - FastAPI API, MongoDB/GridFS storage, Redis cache helpers, and a background audio-analysis worker.

## Runtime Architecture

1. The React app uploads audio through `POST /songs/upload`.
2. FastAPI stores the uploaded file directly in MongoDB GridFS and stores song metadata in the `songs` collection.
3. A background worker polls MongoDB for songs with `analysis_status: pending`.
4. The worker reads the audio bytes from GridFS, calculates hashes, extracts audio metadata, and updates the song document.
5. The frontend reads song metadata from the API and streams audio through `GET /songs/{id}/stream`.

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
