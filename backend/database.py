import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017/spotify_clone")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "spotify_clone")

client = AsyncIOMotorClient(MONGO_URL)
db = client[MONGO_DB_NAME]
fs_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="songs_files")


async def ping_database():
    await client.admin.command("ping")
