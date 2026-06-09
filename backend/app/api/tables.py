import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.table import Table
from app.schemas.table import TableOut, TableUpdate
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["tables"])


@router.get("/{venue_id}/tables", response_model=dict)
async def list_tables(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Table).where(Table.venue_id == venue_id).order_by(Table.number))
    return {"tables": [TableOut.model_validate(t) for t in result.scalars().all()]}


@router.patch("/{venue_id}/tables/{table_id}", response_model=TableOut)
async def patch_table(venue_id: uuid.UUID, table_id: uuid.UUID, data: TableUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Table).where(Table.id == table_id, Table.venue_id == venue_id))
    table = result.scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(table, field, value)
    await db.commit()
    await db.refresh(table)
    return TableOut.model_validate(table)
