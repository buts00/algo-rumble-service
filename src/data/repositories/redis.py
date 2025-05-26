import os
from typing import Any, Dict, List, Union

from fastapi import HTTPException
from redis.asyncio import Redis  # Use async Redis client
from src.config import Config


class MockRedis:
    """A mock Redis implementation for testing purposes with async support."""

    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.expiry: Dict[str, int] = {}
        self.sorted_sets: Dict[str, List[tuple]] = {}

    async def setex(self, name: str, time: int, value: str) -> None:
        self.data[name] = value
        self.expiry[name] = time

    async def set(self, name: str, value: str, ex: int = None) -> None:
        self.data[name] = value
        if ex:
            self.expiry[name] = ex

    async def get(self, name: str) -> Any:
        return self.data.get(name)

    async def exists(self, name: str) -> bool:
        return name in self.data

    async def incr(self, name: str) -> int:
        if name not in self.data:
            self.data[name] = 0
        self.data[name] = int(self.data[name]) + 1
        return self.data[name]

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        pass

    async def zadd(self, name: str, mapping: Dict[str, float]) -> None:
        if name not in self.sorted_sets:
            self.sorted_sets[name] = []
        for value, score in mapping.items():
            self.sorted_sets[name].append((value, score))
        self.sorted_sets[name].sort(key=lambda x: x[1])

    async def zrange(self, name: str, start: int, end: int) -> List[str]:
        if name not in self.sorted_sets:
            return []
        return [item[0] for item in self.sorted_sets[name][start : end + 1]]

    async def zrem(self, name: str, value: str) -> int:
        if name not in self.sorted_sets:
            return 0
        original_len = len(self.sorted_sets[name])
        self.sorted_sets[name] = [
            item for item in self.sorted_sets[name] if item[0] != value
        ]
        return original_len - len(self.sorted_sets[name])

    async def delete(self, name: str) -> int:
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
    """A singleton Redis client for interacting with Redis asynchronously."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RedisClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.redis = None
        self.JTI_EXPIRY = Config.JWT_ACCESS_TOKEN_EXPIRY
        self._connected = False

    async def connect(self):
        if self.redis is None:
            try:
                if "PYTEST_CURRENT_TEST" in os.environ:
                    self.redis = MockRedis()
                    self._connected = True
                    return

                self.redis = Redis(
                    host=Config.REDIS_HOST,
                    port=Config.REDIS_PORT,
                    db=0,
                    password=Config.REDIS_PASSWORD,
                    decode_responses=True,
                )
                await self.redis.ping()  # Async ping
                self._connected = True
            except Exception as e:
                if "PYTEST_CURRENT_TEST" in os.environ:
                    self.redis = MockRedis()
                    self._connected = True
                else:
                    raise HTTPException(
                        status_code=500, detail=f"Redis connection error: {str(e)}"
                    )

    async def close(self):
        if self.redis:
            await self.redis.close()

    async def get(self, name: str) -> Any:
        if not self._connected:
            await self.connect()
        try:
            return await self.redis.get(name)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    async def set(self, name: str, value: str, ex: int = None) -> None:
        if not self._connected:
            await self.connect()
        try:
            await self.redis.set(name=name, value=value, ex=ex)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    async def exists(self, name: str) -> bool:
        if not self._connected:
            await self.connect()
        try:
            return await self.redis.exists(name)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    async def incr(self, name: str) -> int:
        if not self._connected:
            await self.connect()
        try:
            return await self.redis.incr(name)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    async def add_jti_to_blocklist(self, jti: str) -> None:
        if not self._connected:
            await self.connect()
        try:
            await self.redis.setex(
                name=f"jti:{jti}", time=self.JTI_EXPIRY, value="revoked"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    async def token_in_blocklist(self, jti: str) -> bool:
        if not self._connected:
            await self.connect()
        try:
            return await self.redis.exists(f"jti:{jti}")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    async def zadd(self, name: str, mapping: Dict[str, float]) -> None:
        if not self._connected:
            await self.connect()
        try:
            await self.redis.zadd(name, mapping)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    async def zrange(self, name: str, start: int, end: int) -> List[str]:
        if not self._connected:
            await self.connect()
        try:
            return await self.redis.zrange(name, start, end)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    async def zrem(self, name: str, value: Union[str, bytes]) -> int:
        if not self._connected:
            await self.connect()
        try:
            return await self.redis.zrem(name, value)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )

    async def delete(self, name: str) -> int:
        if not self._connected:
            await self.connect()
        try:
            return await self.redis.delete(name)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Redis operation failed: {str(e)}"
            )


redis_client = RedisClient()
