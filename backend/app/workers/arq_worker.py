import uuid

from app.core.arq_queue import _redis_settings


async def run_parse_job(ctx: dict, job_id: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.workers.parser import run_parse_job as execute_parse_job

    async with AsyncSessionLocal() as db:
        await execute_parse_job(db, uuid.UUID(job_id))


class WorkerSettings:
    functions = [run_parse_job]
    redis_settings = _redis_settings()
    max_jobs = 5
    job_timeout = 300  # 5 min — Playwright on JS-heavy SPAs needs up to 2-3 min
    max_tries = 2
