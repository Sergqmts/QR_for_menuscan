from pydantic import BaseModel
import uuid
from datetime import datetime


class CategoryCreate(BaseModel):
    name: str
    slug: str
    sort_order: int = 0
    is_visible: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    is_visible: bool | None = None


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    sort_order: int
    is_visible: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CategoryReorder(BaseModel):
    category_ids: list[uuid.UUID]
