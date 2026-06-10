import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dish import Dish
from app.schemas.dish import DishCreate, DishUpdate, DishOut, UploadUrlOut
from app.services.venue_service import get_venue_or_404
from app.services.qr_service import get_presigned_upload_url

router = APIRouter(prefix="/venues", tags=["dishes"])


@router.post("/{venue_id}/dishes", response_model=DishOut, status_code=201)
async def create_dish(venue_id: uuid.UUID, data: DishCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    dish = Dish(id=uuid.uuid4(), venue_id=venue_id, **data.model_dump())
    db.add(dish)
    await db.commit()
    await db.refresh(dish)
    return DishOut.model_validate(dish)


@router.get("/{venue_id}/dishes", response_model=dict)
async def list_dishes(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Dish).where(Dish.venue_id == venue_id).order_by(Dish.sort_order))
    return {"dishes": [DishOut.model_validate(d) for d in result.scalars().all()]}


@router.patch("/{venue_id}/dishes/{dish_id}", response_model=DishOut)
async def patch_dish(venue_id: uuid.UUID, dish_id: uuid.UUID, data: DishUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Dish).where(Dish.id == dish_id, Dish.venue_id == venue_id))
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(dish, field, value)
    await db.commit()
    await db.refresh(dish)
    return DishOut.model_validate(dish)


@router.delete("/{venue_id}/dishes/{dish_id}", status_code=204)
async def delete_dish(venue_id: uuid.UUID, dish_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Dish).where(Dish.id == dish_id, Dish.venue_id == venue_id))
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    await db.delete(dish)
    await db.commit()


@router.post("/{venue_id}/dishes/{dish_id}/upload-url", response_model=UploadUrlOut)
async def get_upload_url(
    venue_id: uuid.UUID,
    dish_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Dish).where(Dish.id == dish_id, Dish.venue_id == venue_id))
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    key = f"dishes/{venue_id}/{dish_id}.jpg"
    upload_url, image_url = get_presigned_upload_url(key)
    return {"upload_url": upload_url, "image_url": image_url}
