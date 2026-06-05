import hashlib
import os
import tempfile
import time

from bson import ObjectId
from gridfs import GridFSBucket
from pymongo import MongoClient, ReturnDocument
from tinytag import TinyTag

MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017/spotify_clone")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "spotify_clone")

mongo = MongoClient(MONGO_URL)
db = mongo[MONGO_DB_NAME]
fs_bucket = GridFSBucket(db, bucket_name="songs_files")

print(f"Worker started against database: {MONGO_DB_NAME}")

while True:
    song_id = None

    try:
        song = db.songs.find_one_and_update(
            {
                "analysis_status": "pending",
                "file_id": {"$exists": True},
            },
            {
                "$set": {
                    "analysis_status": "processing",
                    "processing_started_at": time.time(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not song:
            print("No pending songs...")
            time.sleep(5)
            continue

        song_id = str(song["_id"])
        file_id = song["file_id"]
        if not isinstance(file_id, ObjectId):
            file_id = ObjectId(file_id)

        print(f"Processing: {song_id}")

        grid_out = fs_bucket.open_download_stream(file_id)
        file_bytes = grid_out.read()
        file_size = len(file_bytes)

        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        md5_hash = hashlib.md5(file_bytes).hexdigest()

        suffix = os.path.splitext(song.get("filename") or "uploaded.mp3")[1] or ".mp3"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            tag = TinyTag.get(tmp_path)
        finally:
            os.unlink(tmp_path)

        duplicate = db.songs.find_one(
            {
                "hash": sha256_hash,
                "_id": {"$ne": ObjectId(song_id)},
            }
        )

        duration_seconds = tag.duration
        update_data = {
            "hash": sha256_hash,
            "md5_hash": md5_hash,
            "file_size": file_size,
            "analysis_status": "done",
            "processed_at": time.time(),
            "duration_seconds": duration_seconds,
            "duration": round(duration_seconds) if duration_seconds is not None else None,
            "audio_title": tag.title,
            "audio_artist": tag.artist,
            "audio_album": tag.album,
            "audio_bitrate": tag.bitrate,
            "audio_samplerate": tag.samplerate,
            "audio_channels": tag.channels,
            "audio_genre": tag.genre,
            "audio_year": tag.year,
            "is_duplicate": bool(duplicate),
        }

        if duplicate:
            update_data["duplicate_of"] = str(duplicate["_id"])

        db.songs.update_one({"_id": ObjectId(song_id)}, {"$set": update_data})
        print(f"Finished: {song_id}")

    except Exception as e:
        print("ERROR:", e)
        if song_id:
            db.songs.update_one(
                {"_id": ObjectId(song_id)},
                {
                    "$set": {
                        "analysis_status": "failed",
                        "error": str(e),
                    }
                },
            )
        time.sleep(2)
