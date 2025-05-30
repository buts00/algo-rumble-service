from src.storage.repositories.redis import RedisClient, redis_client


def get_redis_client() -> RedisClient:
    """Get the singleton RedisClient instance."""
    if not redis_client:
        raise RuntimeError("RedisClient is not initialized")
    return redis_client
