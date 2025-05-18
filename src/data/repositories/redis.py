import os
from typing import Any, Dict

import redis
from fastapi import HTTPException

from src.config import Config


class MockRedis:
    """A simple mock Redis implementation for testing."""

    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.expiry: Dict[str, int] = {}

    def setex(self, name: str, time: int, value: str) -> None:
        """Set a key with expiration."""
        self.data[name] = value
        self.expiry[name] = time

    def set(self, name: str, value: str, ex: int = None) -> None:
        """Set a key with optional expiration."""
        self.data[name] = value
        if ex:
            self.expiry[name] = ex

    def get(self, name: str) -> Any:
        """Get a key's value."""
        return self.data.get(name)

    def exists(self, name: str) -> bool:
        """Check if a key exists."""
        return name in self.data

    def incr(self, name: str) -> int:
        """Increment a key's value."""
        if name not in self.data:
            self.data[name] = 0
        self.data[name] = int(self.data[name]) + 1
        return self.data[name]

    def ping(self) -> bool:
        """Mock ping method."""
        return True

    def close(self) -> None:
        """Mock close method."""
        pass


class RedisClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RedisClient, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.redis = None
        self.JTI_EXPIRY = Config.JWT_ACCESS_TOKEN_EXPIRY
        self._connected = False
        # Don't connect immediately, use lazy initialization
        # This allows tests to run without Redis

    def connect(self):
        if self.redis is None:
            try:
                # Check if we're running tests (pytest sets this environment variable)
                if "PYTEST_CURRENT_TEST" in os.environ:
                    # Use a mock implementation for testing
                    self.redis = MockRedis()
                    self._connected = True
                    return

                self.redis = redis.Redis(
                    host=Config.REDIS_HOST,
                    port=Config.REDIS_PORT,
                    db=0,
                    password=Config.REDIS_PASSWORD,
                    decode_responses=True,
                )
                self.redis.ping()
                self._connected = True
            except redis.ConnectionError as e:
                # If we're running tests, use a mock implementation
                if "PYTEST_CURRENT_TEST" in os.environ:
                    self.redis = MockRedis()
                    self._connected = True
                else:
                    raise HTTPException(
                        status_code=500, detail=f"Redis connection error: {str(e)}"
                    )

    def close(self):
        if self.redis:
            self.redis.close()

    def get(self, name: str) -> Any:
        # Ensure we're connected before using Redis
        if not self._connected:
            self.connect()

        try:
            return self.redis.get(name)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def set(self, name: str, value: str, ex: int = None) -> None:
        # Ensure we're connected before using Redis
        if not self._connected:
            self.connect()

        try:
            self.redis.set(name=name, value=value, ex=ex)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def exists(self, name: str) -> bool:
        # Ensure we're connected before using Redis
        if not self._connected:
            self.connect()

        try:
            return self.redis.exists(name)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def incr(self, name: str) -> int:
        # Ensure we're connected before using Redis
        if not self._connected:
            self.connect()

        try:
            return self.redis.incr(name)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def add_jti_to_blocklist(self, jti: str) -> None:
        # Ensure we're connected before using Redis
        if not self._connected:
            self.connect()

        try:
            self.redis.setex(name=f"jti:{jti}", time=self.JTI_EXPIRY, value="revoked")
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def token_in_blocklist(self, jti: str) -> bool:
        # Ensure we're connected before using Redis
        if not self._connected:
            self.connect()

        try:
            return self.redis.exists(f"jti:{jti}")
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )


# Create a singleton instance, but don't connect immediately
redis_client = RedisClient()