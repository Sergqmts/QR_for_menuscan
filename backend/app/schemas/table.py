from pydantic import BaseModel
import uuid
from datetime import datetime


class TableOut(BaseModel):
    id: uuid.UUID
    number: int
    label: str | None
    qr_code_url: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TableUpdate(BaseModel):
    label: str | None = None
    is_active: bool | None = None
