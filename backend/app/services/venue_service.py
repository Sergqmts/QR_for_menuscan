import uuid
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.venue import Venue
from app.models.table import Table
from app.schemas.venue import VenueCreate, VenueUpdate


def _slugify(name: str) -> str:
    table = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"zh",
        "з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o",
        "п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"kh","ц":"ts",
        "ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"
    }
    slug = name.lower()
    slug = re.sub(r"[а-яё]", lambda m: table.get(m.group(), ""), slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "venue"


async def create_venue(db: AsyncSession, owner_id: uuid.UUID, data: VenueCreate) -> tuple[Venue, uuid.UUID | None]:
    base_slug = _slugify(data.name)
    slug = base_slug
    counter = 1
    while True:
        existing = await db.execute(select(Venue).where(Venue.slug == slug))
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    venue = Venue(
        id=uuid.uuid4(),
        owner_id=owner_id,
        name=data.name,
        slug=slug,
        website_url=data.website_url,
        address=data.address,
        cuisine_type=data.cuisine_type,
        table_count=data.table_count,
        parse_status="pending" if not data.website_url else "parsing",
    )
    db.add(venue)
    await db.flush()

    for n in range(1, data.table_count + 1):
        db.add(Table(id=uuid.uuid4(), venue_id=venue.id, number=n, label=f"Стол {n}"))

    job_id = None
    if data.website_url:
        from app.models.parse_job import ParseJob
        job = ParseJob(id=uuid.uuid4(), venue_id=venue.id, source_url=data.website_url, status="queued")
        db.add(job)
        job_id = job.id

    await db.commit()
    await db.refresh(venue)

    if job_id:
        import asyncio
        from app.workers.parser import run_parse_job
        from app.core.database import AsyncSessionLocal
        async def _run():
            async with AsyncSessionLocal() as bg_db:
                await run_parse_job(bg_db, job_id)
        asyncio.create_task(_run())

    return venue, job_id


async def get_venue_or_404(db: AsyncSession, venue_id: uuid.UUID, owner_id: uuid.UUID) -> Venue:
    result = await db.execute(select(Venue).where(Venue.id == venue_id, Venue.owner_id == owner_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")
    return venue


async def update_venue(db: AsyncSession, venue: Venue, data: VenueUpdate) -> Venue:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(venue, field, value)
    await db.commit()
    await db.refresh(venue)
    return venue
