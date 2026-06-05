from bson import ObjectId
from minio import Minio
from pymongo import MongoClient, ReturnDocument
import hashlib
import time
import os
from tinytag import TinyTag
import tempfile

mongo = MongoClient("mongodb://mongo:27017")
db = mongo.spotify

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio1:9000")

minio = Minio(
    MINIO_ENDPOINT,
    access_key="minio",
    secret_key="minio123",
    secure=False
)

print("Worker started...")

while True:

    try:

        song = db.songs.find_one_and_update(
            {
                "analysis_status": "pending"
            },
            {
                "$set": {
                    "analysis_status": "processing",
                    "processing_started_at": time.time()
                }
            },
            return_document=ReturnDocument.AFTER
        )

        if not song:
            print("No pending songs...")
            time.sleep(5)
            continue

        song_id = str(song["_id"])

        print(f"Processing: {song_id}")

        bucket = song["bucket"]
        file_key = song["file_key"]

        response = minio.get_object(bucket, file_key)
        file_bytes = response.read()
        response.close()

        file_size = len(file_bytes)

        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        md5_hash = hashlib.md5(file_bytes).hexdigest()

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        tag = TinyTag.get(tmp_path)

        os.unlink(tmp_path)

        duplicate = db.songs.find_one({
            "hash": sha256_hash,
            "_id": {"$ne": ObjectId(song_id)}
        })

        update_data = {
            "hash": sha256_hash,
            "md5_hash": md5_hash,
            "file_size": file_size,
            "analysis_status": "done",
            "processed_at": time.time(),
            "duration_seconds": tag.duration,
            "audio_title": tag.title,
            "audio_artist": tag.artist,
            "audio_album": tag.album,
            "audio_bitrate": tag.bitrate,
            "audio_samplerate": tag.samplerate,
            "audio_channels": tag.channels,
            "audio_genre": tag.genre,
            "audio_year": tag.year,
        }

        if duplicate:
            update_data["is_duplicate"] = True
            update_data["duplicate_of"] = str(duplicate["_id"])
        else:
            update_data["is_duplicate"] = False

        db.songs.update_one(
            {"_id": ObjectId(song_id)},
            {"$set": update_data}
        )

        print(f"Finished: {song_id}")

    except Exception as e:

        print("ERROR:", e)

        try:
            db.songs.update_one(
                {"_id": ObjectId(song_id)},
                {
                    "$set": {
                        "analysis_status": "failed",
                        "error": str(e)
                    }
                }
            )
        except:
            pass

        time.sleep(2)
