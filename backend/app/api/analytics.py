import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.analytics import AnalyticsOut
from app.services.analytics_service import get_analytics
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["analytics"])


@router.get("/{venue_id}/analytics", response_model=AnalyticsOut)
async def analytics(
    venue_id: uuid.UUID,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        from_dt = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc) if from_date else datetime.now(timezone.utc) - timedelta(days=30)
        to_dt = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc) if to_date else datetime.now(timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO 8601 (e.g. 2026-01-15)")
    await get_venue_or_404(db, venue_id, user.id)
    return await get_analytics(db, venue_id, from_dt, to_dt)
