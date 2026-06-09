import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.venue import Venue
from app.schemas.venue import VenueCreate, VenueUpdate, VenueOut, VenueCreateResponse
from app.services.venue_service import create_venue, get_venue_or_404, update_venue

router = APIRouter(prefix="/venues", tags=["venues"])


@router.post("", response_model=VenueCreateResponse, status_code=202)
async def create(data: VenueCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    venue, job_id = await create_venue(db, user.id, data)
    return VenueCreateResponse(venue=VenueOut.model_validate(venue), parse_job_id=job_id)


@router.get("", response_model=dict)
async def list_venues(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Venue).where(Venue.owner_id == user.id))
    return {"venues": [VenueOut.model_validate(v) for v in result.scalars().all()]}


@router.get("/{venue_id}", response_model=VenueOut)
async def get_venue(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return VenueOut.model_validate(await get_venue_or_404(db, venue_id, user.id))


@router.patch("/{venue_id}", response_model=VenueOut)
async def patch_venue(venue_id: uuid.UUID, data: VenueUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    venue = await get_venue_or_404(db, venue_id, user.id)
    return VenueOut.model_validate(await update_venue(db, venue, data))
