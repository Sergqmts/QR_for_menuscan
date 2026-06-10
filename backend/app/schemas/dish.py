from pydantic import BaseModel
from decimal import Decimal
import uuid
from datetime import datetime


class DishCreate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str
    description: str | None = None
    price: Decimal
    weight: str | None = None
    calories: str | None = None
    tags: list[str] = []
    allergens: list[str] = []
    is_available: bool = True
    sort_order: int = 0


class DishUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = None
    description: str | None = None
    price: Decimal | None = None
    weight: str | None = None
    calories: str | None = None
    tags: list[str] | None = None
    allergens: list[str] | None = None
    is_available: bool | None = None
    sort_order: int | None = None


class DishOut(BaseModel):
    id: uuid.UUID
    venue_id: uuid.UUID
    category_id: uuid.UUID | None
    name: str
    description: str | None
    price: Decimal
    weight: str | None
    calories: str | None
    image_url: str | None
    tags: list
    allergens: list
    is_available: bool
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadUrlOut(BaseModel):
    upload_url: str
    image_url: str
