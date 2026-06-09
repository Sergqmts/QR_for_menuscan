from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.menu import PublicMenuOut
from app.services.menu_service import get_public_menu

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("/{venue_slug}", response_model=PublicMenuOut)
async def get_menu(venue_slug: str, db: AsyncSession = Depends(get_db)):
    return await get_public_menu(db, venue_slug)
