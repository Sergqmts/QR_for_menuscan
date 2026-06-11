import uuid

from arq.connections import RedisSettings
from urllib.parse import urlparse


async def run_parse_job(ctx: dict, job_id: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.workers.parser import run_parse_job as execute_parse_job

    async with AsyncSessionLocal() as db:
        await execute_parse_job(db, uuid.UUID(job_id))


def _redis_settings() -> RedisSettings:
    from app.core.config import settings
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int((parsed.path or "/0").lstrip("/") or 0),
    )


class WorkerSettings:
    functions = [run_parse_job]
    redis_settings = _redis_settings()
    max_jobs = 5
    job_timeout = 120
    max_tries = 3
