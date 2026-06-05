import redis
import json
import pickle
from functools import wraps
import os
from datetime import timedelta

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True  
)

def test_connection():
    """Testiraj Redis konekciju"""
    try:
        return redis_client.ping()
    except:
        return False

def cache_json(key: str, ttl_seconds: int = 300):
    """Decorator za cache JSON odgovora"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"json:{key}:{str(kwargs)}"
            
            cached = redis_client.get(cache_key)
            if cached:
                print(f" Cache HIT: {cache_key}")
                return json.loads(cached)
            
            
            print(f" Cache MISS: {cache_key}")
            result = await func(*args, **kwargs)
            
            if result:
                redis_client.setex(
                    cache_key,
                    ttl_seconds,
                    json.dumps(result, default=str)
                )
                print(f"Cached: {cache_key} for {ttl_seconds}s")
            
            return result
        return wrapper
    return decorator

def get_cached(key: str):
    """Dohvati podatak iz cachea"""
    cached = redis_client.get(key)
    return json.loads(cached) if cached else None

def set_cached(key: str, value, ttl_seconds: int = 300):
    """Spremi podatak u cache"""
    redis_client.setex(
        key,
        ttl_seconds,
        json.dumps(value, default=str)
    )

def delete_cached(pattern: str):
    """Obriši cache po patternu"""
    keys = redis_client.keys(pattern)
    if keys:
        redis_client.delete(*keys)
        print(f"Deleted cache keys: {pattern} ({len(keys)} keys)")

def invalidate_song_cache(song_id: str = None):
    """Invalidiraj cache za pjesme"""
    if song_id:
        delete_cached(f"json:song:*{song_id}*")
        delete_cached(f"json:songs:*{song_id}*")
    else:
        delete_cached("json:song:*")
        delete_cached("json:songs:*")


class CacheKeys:
    @staticmethod
    def song_list(page: int = 1, limit: int = 10, search: str = ""):
        return f"json:songs:page:{page}:limit:{limit}:search:{search}"
    
    @staticmethod
    def song_detail(song_id: str):
        return f"json:song:{song_id}"
    
    @staticmethod
    def song_analysis(song_id: str):
        return f"json:song_analysis:{song_id}"
    
    @staticmethod
    def song_stream(song_id: str):
        return f"binary:song_stream:{song_id}"