from urllib.parse import urlparse

from arq import create_pool
from arq.connections import RedisSettings

_pool = None


def _redis_settings() -> RedisSettings:
    from app.core.config import settings
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int((parsed.path or "/0").lstrip("/") or 0),
    )


async def get_arq_pool():
    global _pool
    if _pool is None:
        _pool = await create_pool(_redis_settings())
    return _pool
