import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.schemas.analytics import AnalyticsOut
from app.services.analytics_service import get_analytics
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["analytics"])

_bearer = HTTPBearer(auto_error=False)


async def _get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    return result.scalar_one_or_none()


@router.get("/{venue_id}/analytics", response_model=AnalyticsOut)
async def analytics(
    venue_id: uuid.UUID,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(_get_optional_user),
):
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
    await get_venue_or_404(db, venue_id, user.id)
    now = datetime.now(timezone.utc)
    from_dt = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc) if from_date else now - timedelta(days=30)
    to_dt = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc) if to_date else now
    return await get_analytics(db, venue_id, from_dt, to_dt)
