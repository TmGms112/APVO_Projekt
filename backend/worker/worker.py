import hashlib
import os
import time

from bson import ObjectId
from gridfs import GridFSBucket
from pymongo import MongoClient, ReturnDocument

from ml_features import extract_audio_features
from storage import get_file

MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017/spotify")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "spotify")

mongo = MongoClient(MONGO_URL)
db = mongo[MONGO_DB_NAME]
fs_bucket = GridFSBucket(db, bucket_name="songs_files")

print(f"Worker started against database: {MONGO_DB_NAME}")


def read_song_bytes(song):
    if song.get("file_id"):
        file_id = song["file_id"]
        if not isinstance(file_id, ObjectId):
            file_id = ObjectId(file_id)
        return fs_bucket.open_download_stream(file_id).read()

    if song.get("file_key"):
        response = get_file(song["file_key"], song.get("bucket") or "songs")
        try:
            return response.read()
        finally:
            response.close()

    raise RuntimeError("Song has neither GridFS file_id nor legacy file_key")


while True:
    song_id = None

    try:
        song = db.songs.find_one_and_update(
            {
                "$and": [
                    {"features": {"$exists": False}},
                    {"$or": [{"analysis_status": "pending"}, {"status": "uploaded"}, {"analysis_status": {"$exists": False}}]},
                    {"$or": [{"file_id": {"$exists": True}}, {"file_key": {"$exists": True}}]},
                ]
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
        print(f"Processing: {song_id}")

        file_bytes = read_song_bytes(song)
        file_size = len(file_bytes)

        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        md5_hash = hashlib.md5(file_bytes).hexdigest()
        features, feature_vector, metadata = extract_audio_features(
            file_bytes,
            song.get("filename") or song.get("title") or song.get("file_key") or "uploaded-audio",
        )

        duplicate = db.songs.find_one(
            {
                "hash": sha256_hash,
                "_id": {"$ne": ObjectId(song_id)},
            }
        )

        duration_seconds = features.get("duration_seconds")
        update_data = {
            "hash": sha256_hash,
            "md5_hash": md5_hash,
            "file_size": file_size,
            "analysis_status": "done",
            "status": "processed",
            "processed_at": time.time(),
            "duration_seconds": duration_seconds,
            "duration": round(duration_seconds) if duration_seconds is not None else None,
            "features": features,
            "feature_vector": feature_vector,
            "feature_names": list(features.keys()),
            "is_duplicate": bool(duplicate),
            **metadata,
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
