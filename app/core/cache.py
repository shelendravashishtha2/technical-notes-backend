from __future__ import annotations

import time
from typing import Any

import orjson
try:
    import redis.asyncio as redis
except ModuleNotFoundError:  # Optional dependency during local static checks.
    redis = None  # type: ignore[assignment]

from app.core.config import settings


class JsonCache:
    def __init__(self) -> None:
        self._redis = None
        self._memory: dict[str, tuple[float, bytes]] = {}

    async def connect(self) -> None:
        if settings.redis_url and redis is not None:
            self._redis = redis.from_url(settings.redis_url, encoding=None, decode_responses=False)
            await self._redis.ping()

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    async def get(self, key: str) -> Any | None:
        if self._redis:
            value = await self._redis.get(key)
            if value is None:
                return None
            return orjson.loads(value)

        item = self._memory.get(key)
        if not item:
            return None
        expires_at, payload = item
        if expires_at < time.time():
            self._memory.pop(key, None)
            return None
        return orjson.loads(payload)

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        payload = orjson.dumps(value, option=orjson.OPT_SERIALIZE_UUID)
        if self._redis:
            await self._redis.set(key, payload, ex=ttl_seconds)
            return
        self._memory[key] = (time.time() + ttl_seconds, payload)

    async def delete_prefix(self, prefix: str) -> None:
        if self._redis:
            async for key in self._redis.scan_iter(match=f"{prefix}*"):
                await self._redis.delete(key)
            return
        for key in list(self._memory.keys()):
            if key.startswith(prefix):
                self._memory.pop(key, None)


cache = JsonCache()
