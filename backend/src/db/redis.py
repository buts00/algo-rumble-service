import redis
from backend.src.config import Config
from fastapi import HTTPException


class RedisClient:
    def __init__(self):
        self.redis = None
        self.JTI_EXPIRY = Config.JWT_ACCESS_TOKEN_EXPIRY  # Час життя токена з конфігу

    def connect(self):
        try:
            self.redis = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=0,
                decode_responses=True,
            )

            self.redis.ping()
        except redis.ConnectionError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis connection error: {str(e)}"
            )

    def close(self):
        if self.redis:
            self.redis.close()

    def add_jti_to_blocklist(self, jti: str) -> None:
        try:
            self.redis.setex(name=f"jti:{jti}", time=self.JTI_EXPIRY, value="revoked")
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def token_in_blocklist(self, jti: str) -> bool:
        try:
            return self.redis.exists(f"jti:{jti}") == 1
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )


redis_client = RedisClient()
redis_client.connect()
