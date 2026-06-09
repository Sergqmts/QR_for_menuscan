import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.parse_job import ParseJob
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["parsing"])


@router.get("/{venue_id}/parse-status")
async def parse_status(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(
        select(ParseJob).where(ParseJob.venue_id == venue_id).order_by(ParseJob.id.desc()).limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="No parse job found")
    return {
        "job_id": job.id,
        "status": job.status,
        "dishes_found": job.dishes_found,
        "error_message": job.error_message,
        "finished_at": job.finished_at,
    }


@router.post("/{venue_id}/reparse", status_code=202)
async def reparse(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.venue import Venue
    venue = await get_venue_or_404(db, venue_id, user.id)
    if not venue.website_url:
        raise HTTPException(status_code=400, detail="No website URL set")

    job = ParseJob(id=uuid.uuid4(), venue_id=venue_id, source_url=venue.website_url, status="queued")
    db.add(job)
    venue.parse_status = "parsing"
    await db.commit()
    await db.refresh(job)

    from app.workers.parser import run_parse_job
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as bg_db:
            await run_parse_job(bg_db, job.id)

    asyncio.create_task(_run())
    return {"parse_job_id": job.id, "status": "queued"}
