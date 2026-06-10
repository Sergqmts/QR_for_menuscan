from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.schemas.menu import PublicMenuOut
from app.schemas.order import PublicTableOut
from app.services.menu_service import get_public_menu
from app.models.venue import Venue
from app.models.table import Table

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("/{venue_slug}/table/{table_number}", response_model=PublicTableOut)
async def get_table_by_number(
    venue_slug: str, table_number: int, db: AsyncSession = Depends(get_db)
):
    venue_result = await db.execute(
        select(Venue).where(Venue.slug == venue_slug, Venue.is_active == True)
    )
    venue = venue_result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    table_result = await db.execute(
        select(Table).where(Table.venue_id == venue.id, Table.number == table_number)
    )
    table = table_result.scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    return PublicTableOut.model_validate(table)


@router.get("/{venue_slug}", response_model=PublicMenuOut)
async def get_menu(venue_slug: str, db: AsyncSession = Depends(get_db)):
    return await get_public_menu(db, venue_slug)
