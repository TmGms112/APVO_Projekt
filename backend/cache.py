import json
import os
from functools import wraps

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


def test_connection():
    try:
        return redis_client.ping()
    except Exception:
        return False


def cache_json(key: str, ttl_seconds: int = 300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"json:{key}:{str(kwargs)}"
            cached = get_cached(cache_key)
            if cached is not None:
                return cached

            result = await func(*args, **kwargs)
            set_cached(cache_key, result, ttl_seconds)
            return result

        return wrapper

    return decorator


def get_cached(key: str):
    try:
        cached = redis_client.get(key)
        return json.loads(cached) if cached else None
    except Exception:
        return None


def set_cached(key: str, value, ttl_seconds: int = 300):
    try:
        redis_client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception:
        pass


def delete_cached(pattern: str):
    try:
        keys = list(redis_client.scan_iter(pattern))
        if keys:
            redis_client.delete(*keys)
    except Exception:
        pass


def invalidate_song_cache(song_id: str | None = None):
    if song_id:
        delete_cached(f"json:song:*{song_id}*")
        delete_cached(f"json:songs:*{song_id}*")
    else:
        delete_cached("json:song:*")
        delete_cached("json:songs:*")


class CacheKeys:
    @staticmethod
    def song_list(search: str = ""):
        return f"json:songs:list:{search}"

    @staticmethod
    def song_detail(song_id: str):
        return f"json:song:{song_id}"

    @staticmethod
    def song_analysis(song_id: str):
        return f"json:song_analysis:{song_id}"
