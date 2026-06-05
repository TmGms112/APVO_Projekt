from fastapi import FastAPI
from routers.songs import router as songs_router
from database import db
from motor.motor_asyncio import AsyncIOMotorClient
from routers.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from pymongo.errors import ServerSelectionTimeoutError
import socket
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017/spotify_clone")
print(f"Connecting to MongoDB at: {MONGO_URL}")

try:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client["spotify"]
    print(f"Connected to database: {db.name}")
except Exception as e:
    print(f"MongoDB connection error: {e}")
    db = None


app.include_router(songs_router)
app.include_router(auth_router)

@app.get("/")
async def root():
    return {"message": "Server is running", "routes": ["/songs/upload"]}

@app.get("/test-routes")
async def test_routes():
    return {
        "songs_upload": "POST /songs/upload",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }

app.include_router(songs_router, prefix="/songs", tags=["songs"])

@app.get("/health")
async def health_check():
    try:
        await client.admin.command('ping')
        return {
            "status": "healthy",
            "mongo": "connected",
            "instance": socket.gethostname()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "mongo": "disconnected",
            "error": str(e)
        }
    
@app.get("/instance")
async def instance():
    return {"instance": socket.gethostname()}

@app.on_event("startup")
async def startup():
    max_retries = 20
    for i in range(max_retries):
        try:
            await db.command("ping")
            await db.songs.create_index("title")
            await db.songs.create_index("artist")
            print("Mongo connected & indexes created")
            break
        except Exception as e:
            print(f"Mongo not ready yet ({i+1}/{max_retries}): {e}")
            await asyncio.sleep(3)
    else:
        raise RuntimeError("MongoDB not available after retries")

    

