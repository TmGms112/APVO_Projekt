import os
import uuid
from datetime import datetime
from pymongo import MongoClient
from minio import Minio

print("STARTING SCRIPT")

mongo = MongoClient("mongodb://localhost:27017/")
db = mongo.spotify

print("CONNECTED TO MONGO")

minio = Minio(
    "localhost:9000",
    access_key="minio",
    secret_key="minio123",
    secure=False
)

print("CONNECTED TO MINIO")

print("Bucket exists:", minio.bucket_exists("songs"))

SONGS_FOLDER = "./songs"

files = os.listdir(SONGS_FOLDER)

print("FILES:", files)

for filename in files:

    if not filename.endswith(".mp3"):
        continue

    print("PROCESSING:", filename)

    filepath = os.path.join(SONGS_FOLDER, filename)

    file_key = f"{uuid.uuid4()}.mp3"

    try:

        print("UPLOADING TO MINIO...")

        minio.fput_object(
            "songs",
            file_key,
            filepath,
            content_type="audio/mpeg"
        )

        print("MINIO SUCCESS")

        song = {
            "title": filename,
            "artist": "Unknown Artist",
            "file_key": file_key,
            "bucket": "songs",
            "analysis_status": "pending",
            "uploaded_at": datetime.utcnow()
        }

        result = db.songs.insert_one(song)

        print("MONGO INSERT SUCCESS")
        print("INSERTED ID:", result.inserted_id)

    except Exception as e:

        print("ERROR:")
        print(e)

print("DONE")
