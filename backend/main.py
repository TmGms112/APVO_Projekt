import asyncio
import socket

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import MONGO_DB_NAME, MONGO_URL, client, db
from routers.auth import router as auth_router
from routers.songs import router as songs_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(songs_router)
app.include_router(auth_router)


@app.get("/")
async def root():
    return {
        "message": "Server is running",
        "database": MONGO_DB_NAME,
        "routes": ["/songs", "/songs/upload", "/auth/register", "/auth/login"],
    }


@app.get("/test-routes")
async def test_routes():
    return {
        "songs": "GET /songs/",
        "songs_search": "GET /songs/search?title=&artist=",
        "songs_upload": "POST /songs/upload",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health")
async def health_check():
    try:
        await client.admin.command("ping")
        return {
            "status": "healthy",
            "mongo": "connected",
            "database": MONGO_DB_NAME,
            "instance": socket.gethostname(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "mongo": "disconnected",
            "database": MONGO_DB_NAME,
            "error": str(e),
        }


@app.get("/instance")
async def instance():
    return {"instance": socket.gethostname()}


@app.on_event("startup")
async def startup():
    max_retries = 20
    for i in range(max_retries):
        try:
            await client.admin.command("ping")
            await db.songs.create_index("title")
            await db.songs.create_index("artist")
            await db.songs.create_index("analysis_status")
            await db.users.create_index("username")
            await db.users.create_index("email")
            print(f"Mongo connected at {MONGO_URL}; using database {MONGO_DB_NAME}")
            break
        except Exception as e:
            print(f"Mongo not ready yet ({i + 1}/{max_retries}): {e}")
            await asyncio.sleep(3)
    else:
        raise RuntimeError("MongoDB not available after retries")
