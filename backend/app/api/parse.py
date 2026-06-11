import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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
        "diff_data": job.diff_data,
        "error_message": job.error_message,
        "finished_at": job.finished_at,
    }


@router.post("/{venue_id}/reparse", status_code=202)
async def reparse(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    venue = await get_venue_or_404(db, venue_id, user.id)
    if not venue.website_url:
        raise HTTPException(status_code=400, detail="No website URL set")

    job = ParseJob(id=uuid.uuid4(), venue_id=venue_id, source_url=venue.website_url, status="queued", diff_mode=False)
    db.add(job)
    venue.parse_status = "parsing"
    await db.commit()
    await db.refresh(job)

    from app.core.arq_queue import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("run_parse_job", str(job.id))
    return {"parse_job_id": job.id, "status": "queued"}


@router.post("/{venue_id}/reparse-diff", status_code=202)
async def reparse_diff(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    venue = await get_venue_or_404(db, venue_id, user.id)
    if not venue.website_url:
        raise HTTPException(status_code=400, detail="No website URL set")

    job = ParseJob(id=uuid.uuid4(), venue_id=venue_id, source_url=venue.website_url, status="queued", diff_mode=True)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    from app.core.arq_queue import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("run_parse_job", str(job.id))
    return {"parse_job_id": job.id, "status": "queued"}


class ApplyDiffRequest(BaseModel):
    changes: list[dict]


@router.post("/{venue_id}/parse/apply-diff")
async def apply_diff(
    venue_id: uuid.UUID,
    data: ApplyDiffRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.models.dish import Dish
    from app.models.category import Category

    await get_venue_or_404(db, venue_id, user.id)

    cat_result = await db.execute(
        select(Category).where(Category.venue_id == venue_id, Category.slug == "uncategorized")
    )
    default_cat = cat_result.scalar_one_or_none()

    for change in data.changes:
        action = change.get("action")
        dish_id = change.get("dish_id")

        if action == "update" and dish_id:
            result = await db.execute(select(Dish).where(Dish.id == uuid.UUID(dish_id), Dish.venue_id == venue_id))
            dish = result.scalar_one_or_none()
            if dish:
                if "new_price" in change:
                    dish.price = change["new_price"]
                if "new_weight" in change:
                    dish.weight = change["new_weight"]

        elif action == "add":
            if not default_cat:
                default_cat = Category(id=uuid.uuid4(), venue_id=venue_id, name="Меню", slug="uncategorized", sort_order=0)
                db.add(default_cat)
                await db.flush()
            db.add(Dish(
                id=uuid.uuid4(),
                venue_id=venue_id,
                category_id=default_cat.id,
                name=change["name"],
                price=change.get("new_price", 0),
                weight=change.get("new_weight"),
                description=change.get("description"),
            ))

        elif action == "remove" and dish_id:
            result = await db.execute(select(Dish).where(Dish.id == uuid.UUID(dish_id), Dish.venue_id == venue_id))
            dish = result.scalar_one_or_none()
            if dish:
                dish.is_available = False

    await db.commit()
    return {"ok": True}
