import asyncio
from urllib.parse import urlparse

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

_pool: ArqRedis | None = None
_lock = asyncio.Lock()


def _redis_settings() -> RedisSettings:
    from app.core.config import settings
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int((parsed.path or "/0").lstrip("/") or 0),
    )


async def get_arq_pool() -> ArqRedis:
    global _pool
    async with _lock:
        if _pool is None:
            _pool = await create_pool(_redis_settings())
    return _pool


async def close_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
