import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryOut
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["categories"])


@router.post("/{venue_id}/categories", response_model=CategoryOut, status_code=201)
async def create_category(venue_id: uuid.UUID, data: CategoryCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    cat = Category(id=uuid.uuid4(), venue_id=venue_id, **data.model_dump())
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return CategoryOut.model_validate(cat)


@router.get("/{venue_id}/categories", response_model=dict)
async def list_categories(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Category).where(Category.venue_id == venue_id).order_by(Category.sort_order))
    return {"categories": [CategoryOut.model_validate(c) for c in result.scalars().all()]}


@router.patch("/{venue_id}/categories/{cat_id}", response_model=CategoryOut)
async def patch_category(venue_id: uuid.UUID, cat_id: uuid.UUID, data: CategoryUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Category).where(Category.id == cat_id, Category.venue_id == venue_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(cat, field, value)
    await db.commit()
    await db.refresh(cat)
    return CategoryOut.model_validate(cat)


@router.delete("/{venue_id}/categories/{cat_id}", status_code=204)
async def delete_category(venue_id: uuid.UUID, cat_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Category).where(Category.id == cat_id, Category.venue_id == venue_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    await db.delete(cat)
    await db.commit()
