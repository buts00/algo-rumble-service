import os
from typing import Any, Dict, List, Union

import redis
from fastapi import HTTPException

from src.config import Config


class MockRedis:
    """A mock Redis implementation for testing purposes."""

    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.expiry: Dict[str, int] = {}
        self.sorted_sets: Dict[str, List[tuple]] = {}

    def setex(self, name: str, time: int, value: str) -> None:
        self.data[name] = value
        self.expiry[name] = time

    def set(self, name: str, value: str, ex: int = None) -> None:
        self.data[name] = value
        if ex:
            self.expiry[name] = ex

    def get(self, name: str) -> Any:
        return self.data.get(name)

    def exists(self, name: str) -> bool:
        return name in self.data

    def incr(self, name: str) -> int:
        if name not in self.data:
            self.data[name] = 0
        self.data[name] = int(self.data[name]) + 1
        return self.data[name]

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        pass

    def zadd(self, name: str, mapping: Dict[str, float]) -> None:
        if name not in self.sorted_sets:
            self.sorted_sets[name] = []
        for value, score in mapping.items():
            self.sorted_sets[name].append((value, score))
        self.sorted_sets[name].sort(key=lambda x: x[1])

    def zrange(self, name: str, start: int, end: int) -> List[str]:
        if name not in self.sorted_sets:
            return []
        return [item[0] for item in self.sorted_sets[name][start : end + 1]]

    def zrem(self, name: str, value: str) -> int:
        if name not in self.sorted_sets:
            return 0
        original_len = len(self.sorted_sets[name])
        self.sorted_sets[name] = [
            item for item in self.sorted_sets[name] if item[0] != value
        ]
        return original_len - len(self.sorted_sets[name])

    def delete(self, name: str) -> int:
        if name in self.data:
            del self.data[name]
            if name in self.expiry:
                del self.expiry[name]
            return 1
        if name in self.sorted_sets:
            del self.sorted_sets[name]
            return 1
        return 0


class RedisClient:
    """A singleton Redis client for interacting with Redis."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RedisClient, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.redis = None
        self.JTI_EXPIRY = Config.JWT_ACCESS_TOKEN_EXPIRY
        self._connected = False

    def connect(self):
        if self.redis is None:
            try:
                if "PYTEST_CURRENT_TEST" in os.environ:
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
        if not self._connected:
            self.connect()
        try:
            return self.redis.get(name)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def set(self, name: str, value: str, ex: int = None) -> None:
        if not self._connected:
            self.connect()
        try:
            self.redis.set(name=name, value=value, ex=ex)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def exists(self, name: str) -> bool:
        if not self._connected:
            self.connect()
        try:
            return self.redis.exists(name)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def incr(self, name: str) -> int:
        if not self._connected:
            self.connect()
        try:
            return self.redis.incr(name)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def add_jti_to_blocklist(self, jti: str) -> None:
        if not self._connected:
            self.connect()
        try:
            self.redis.setex(name=f"jti:{jti}", time=self.JTI_EXPIRY, value="revoked")
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def token_in_blocklist(self, jti: str) -> bool:
        if not self._connected:
            self.connect()
        try:
            return self.redis.exists(f"jti:{jti}")
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def zadd(self, name: str, mapping: Dict[str, float]) -> None:
        if not self._connected:
            self.connect()
        try:
            self.redis.zadd(name, mapping)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def zrange(self, name: str, start: int, end: int) -> List[str]:
        if not self._connected:
            self.connect()
        try:
            return self.redis.zrange(name, start, end)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def zrem(self, name: str, value: Union[str, bytes]) -> int:
        if not self._connected:
            self.connect()
        try:
            return self.redis.zrem(name, value)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    def delete(self, name: str) -> int:
        if not self._connected:
            self.connect()
        try:
            return self.redis.delete(name)
        except redis.RedisError as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )


redis_client = RedisClient()
