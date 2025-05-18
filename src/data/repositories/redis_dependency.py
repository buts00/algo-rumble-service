from src.data.repositories.redis import RedisClient


def get_redis_client() -> RedisClient:
    redis_client = RedisClient()
    return redis_client
