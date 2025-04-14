import redis
from src.config import Config
from fastapi import HTTPException


class RedisClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RedisClient, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.redis = None
        self.JTI_EXPIRY = Config.JWT_ACCESS_TOKEN_EXPIRY
        self.connect()

    def connect(self):
        if self.redis is None:
            try:
                self.redis = redis.Redis(
                    host=Config.REDIS_HOST,
                    port=Config.REDIS_PORT,
                    db=0,
                    password=Config.REDIS_PASSWORD,
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
            return self.redis.exists(f"jti:{jti}")
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )


redis_client = RedisClient()
