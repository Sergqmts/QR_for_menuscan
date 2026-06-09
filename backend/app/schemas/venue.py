from pydantic import BaseModel
import uuid
from datetime import datetime


class VenueCreate(BaseModel):
    name: str
    website_url: str | None = None
    table_count: int = 0
    address: str | None = None
    cuisine_type: str | None = None


class VenueUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    cuisine_type: str | None = None
    settings: dict | None = None
    is_active: bool | None = None


class VenueOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    address: str | None
    cuisine_type: str | None
    table_count: int
    parse_status: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VenueCreateResponse(BaseModel):
    venue: VenueOut
    parse_job_id: uuid.UUID | None = None
