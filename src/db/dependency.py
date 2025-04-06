from .redis import RedisClient


def get_redis_client() -> RedisClient:
    return RedisClient()
