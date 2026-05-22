import redis
import os

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

_r = None

def get_redis():
    global _r
    if _r is None:
        _r = redis.Redis.from_url(redis_url, decode_responses=True)
    return _r
