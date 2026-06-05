from datetime import datetime
from io import BytesIO
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from cache import CacheKeys, get_cached, invalidate_song_cache, set_cached
from database import db, fs_bucket
from models.song import CreateSong, UpdateSong


class SongMetaUpdate(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None


router = APIRouter(prefix="/songs", tags=["songs"])


def parse_object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=400, detail="Invalid song id")
    return ObjectId(value)


def serialize_song(song: dict) -> dict:
    song = dict(song)
    song["id"] = str(song.pop("_id"))

    if isinstance(song.get("file_id"), ObjectId):
        song["file_id"] = str(song["file_id"])

    for key, value in list(song.items()):
        if isinstance(value, datetime):
            song[key] = value.isoformat()

    if "duration" not in song and "duration_seconds" in song:
        duration = song.get("duration_seconds")
        song["duration"] = round(duration) if duration is not None else None

    return song


@router.post("/")
async def create_song(song: CreateSong):
    result = await db.songs.insert_one(song.dict(exclude_none=True))
    invalidate_song_cache()
    return {"id": str(result.inserted_id)}


@router.post("/upload")
async def upload_song(
    file: UploadFile = File(...),
    title: str = "",
    artist: str = "",
):
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    filename = file.filename or "uploaded-audio"
    now = datetime.utcnow()

    file_id = await fs_bucket.upload_from_stream(
        filename,
        BytesIO(contents),
        metadata={
            "content_type": file.content_type or "application/octet-stream",
            "title": title or filename,
            "artist": artist or "Unknown Artist",
            "uploaded_at": now,
        },
    )

    song = {
        "title": title or filename,
        "artist": artist or "Unknown Artist",
        "filename": filename,
        "content_type": file.content_type or "application/octet-stream",
        "file_id": file_id,
        "file_size": len(contents),
        "hash": None,
        "analysis_status": "pending",
        "uploaded_at": now,
    }

    result = await db.songs.insert_one(song)
    invalidate_song_cache()

    return {
        "message": "Song uploaded successfully. Audio analysis in progress.",
        "id": str(result.inserted_id),
        "file_id": str(file_id),
        "title": song["title"],
        "artist": song["artist"],
        "analysis_status": song["analysis_status"],
        "status": "processing",
        "details": "Worker will calculate hash and duration from MongoDB/GridFS",
    }


@router.get("/search")
async def search_songs(
    title: Optional[str] = Query(None),
    artist: Optional[str] = Query(None),
):
    cache_key = CacheKeys.song_list(f"title={title or ''}:artist={artist or ''}")
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    query = {}
    if title:
        query["title"] = {"$regex": title, "$options": "i"}
    if artist:
        query["artist"] = {"$regex": artist, "$options": "i"}

    songs = []
    async for song in db.songs.find(query):
        songs.append(serialize_song(song))

    set_cached(cache_key, songs)
    return songs


@router.get("/")
async def get_songs():
    cache_key = CacheKeys.song_list()
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    songs = []
    async for song in db.songs.find():
        songs.append(serialize_song(song))

    set_cached(cache_key, songs)
    return songs


@router.get("/{song_id}/stream")
async def stream_song(song_id: str):
    object_id = parse_object_id(song_id)
    song = await db.songs.find_one({"_id": object_id})
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    if not song.get("file_id"):
        raise HTTPException(status_code=404, detail="Song file not found")

    try:
        grid_out = await fs_bucket.open_download_stream(song["file_id"])
        file_bytes = await grid_out.read()
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Song file not found: {e}") from e

    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=song.get("content_type") or "audio/mpeg",
    )


@router.put("/{song_id}")
async def update_song(song_id: str, song: UpdateSong):
    result = await db.songs.update_one(
        {"_id": parse_object_id(song_id)},
        {"$set": song.dict(exclude_none=True)},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Song not found")

    invalidate_song_cache(song_id)
    return {"status": "updated"}


@router.put("/{id}/meta")
async def update_song_meta(id: str, meta: SongMetaUpdate):
    update_data = {k: v for k, v in meta.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No metadata provided")

    result = await db.songs.update_one(
        {"_id": parse_object_id(id)},
        {"$set": update_data},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Song not found")

    invalidate_song_cache(id)
    return {"message": "Metadata updated", "updated_fields": update_data}


@router.delete("/{song_id}")
async def delete_song(song_id: str):
    object_id = parse_object_id(song_id)
    song = await db.songs.find_one({"_id": object_id})
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    result = await db.songs.delete_one({"_id": object_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Song not found")

    if song.get("file_id"):
        try:
            await fs_bucket.delete(song["file_id"])
        except Exception:
            pass

    invalidate_song_cache(song_id)
    return {"status": "deleted"}


@router.get("/{song_id}/analysis")
async def get_song_analysis(song_id: str):
    cache_key = CacheKeys.song_analysis(song_id)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    song = await db.songs.find_one({"_id": parse_object_id(song_id)})
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    analysis = {
        "song_id": song_id,
        "title": song.get("title"),
        "artist": song.get("artist"),
        "file_id": str(song.get("file_id")) if song.get("file_id") else None,
        "hash": song.get("hash"),
        "file_size_bytes": song.get("file_size"),
        "uploaded_at": song.get("uploaded_at"),
        "analysis_status": song.get("analysis_status", "pending"),
        "status": "processed" if song.get("hash") else "pending",
    }

    if "duration_seconds" in song:
        analysis["duration_seconds"] = song["duration_seconds"]

    for key, value in list(analysis.items()):
        if isinstance(value, datetime):
            analysis[key] = value.isoformat()

    set_cached(cache_key, analysis)
    return analysis
