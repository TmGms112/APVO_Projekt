from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from  pydantic import BaseModel
from storage import upload_file
from models.song import CreateSong, UpdateSong
from database import db
from bson import ObjectId
import uuid
from fastapi.responses import StreamingResponse
from storage import get_file
from typing import Optional
from rabbitmq import send_to_queue
import json
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from io import BytesIO
import traceback

class SongMetaUpdate(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None

router = APIRouter(prefix="/songs")


@router.post("/")
async def create_song(song: CreateSong):
    result = await db.songs.insert_one(song.dict())
    return {"id": str(result.inserted_id)}

@router.post("/upload")
async def upload_song(
    file: UploadFile = File(...),
    title: str = "",
    artist: str = "",
):
    try:
        print(f"Starting upload for: {file.filename}")
        
        contents = await file.read()
        file_size = len(contents)
        print(f" File size: {file_size} bytes")
        
       
        file_id = f"{uuid.uuid4()}.mp3"
        file_stream = BytesIO(contents)
        
        
        print(f" Uploading to MinIO: {file_id}")
        upload_file(
            file_id,
            file_stream,
            file.content_type,
            bucket="songs"
        )
        print(" MinIO upload successful")
        
        
        song = {
            "title": title if title else file.filename,
            "artist": artist if artist else "Unknown Artist",
            "file_key": file_id,
            "bucket": "songs",
            "file_size": file_size,
            "hash": None, 
            "analysis_status": "pending",
            "uploaded_at": datetime.utcnow()
        }
        
        result = await db.songs.insert_one(song)
        song_id = str(result.inserted_id)
        print(f" Saved to database: {song_id}")
        
       
        return {
            "message": "Song uploaded successfully. Audio analysis in progress.",
            "id": song_id,
            "file_key": file_id,
            "status": "processing",
            "details": "Worker will calculate hash and duration"
        }
        
    except Exception as e:
        print(f" Upload failed: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Upload failed: {str(e)}"
        )

@router.get("/songs/search")
async def search_songs(
    title: Optional[str] = Query(None),
    artist: Optional[str] = Query(None),
):
    query = {}

    if title:
        query["title"] = {"$regex": title, "$options": "i"} 

    if artist:
        query["artist"] = {"$regex": artist, "$options": "i"}

    songs = []
    async for song in db.songs.find(query):
        song["_id"] = str(song["_id"])
        songs.append(song)

    return songs


@router.get("/")
async def get_songs():
    songs=[]
    async for song in db.songs.find():
        song["id"] = str(song["_id"])
        del song["_id"]
        songs.append(song)
    return songs

@router.get("/{song_id}/stream")
async def stream_song(song_id: str):
    try:
        song = await db.songs.find_one({"_id": ObjectId(song_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid song id")

    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    song = await db.songs.find_one({"_id": ObjectId(song_id)})
    if not song:
        return {"error": "Not found"}

    file = get_file(song["file_key"])

    return StreamingResponse(
        file,
        media_type="audio/mpeg"
    )

@router.put("/{song_id}")
async def update_song(song_id: str, song: UpdateSong):
    result = await db.songs.update_one(
        {"_id": ObjectId(song_id)},
        {"$set": song.dict(exclude_none=True)}
    )

    if result.matched_count == 0:
        return {"error": "Song not found"}

    return {"status": "updated"}

@router.put("/{id}/meta")
async def update_song_meta(id: str, meta: SongMetaUpdate):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid song ID")

    update_data = {k: v for k, v in meta.dict().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No metadata provided")

    result = await db.songs.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Song not found")

    return {
        "message": "Metadata updated",
        "updated_fields": update_data
    }


@router.delete("/{song_id}")
async def delete_song(song_id: str):
    result = await db.songs.delete_one(
        {"_id": ObjectId(song_id)}
    )

    if result.deleted_count == 0:
        return {"error": "Song not found"}

    return {"status": "deleted"}

@router.get("/{song_id}/analysis")
async def get_song_analysis(song_id: str):
    """Dohvati rezultate analize pjesme"""
    try:
        song = await db.songs.find_one({"_id": ObjectId(song_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid song id")

    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    
    analysis = {
        "song_id": song_id,
        "title": song.get("title"),
        "artist": song.get("artist"),
        "file_key": song.get("file_key"),
        "hash": song.get("hash"),
        "file_size_bytes": song.get("file_size"),
        "uploaded_at": song.get("uploaded_at"),
        "status": "processed" if song.get("hash") else "pending"
    }

    if "duration" in song:
        analysis["duration_seconds"] = song["duration"]
    
    return analysis