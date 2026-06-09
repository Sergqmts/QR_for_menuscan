from pydantic import BaseModel
from decimal import Decimal
import uuid


class PublicDishOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    weight: str | None
    calories: str | None
    image_url: str | None
    tags: list
    allergens: list
    is_available: bool

    model_config = {"from_attributes": True}


class PublicCategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    sort_order: int
    dishes: list[PublicDishOut]


class PublicVenueOut(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    settings: dict


class PublicMenuOut(BaseModel):
    venue: PublicVenueOut
    categories: list[PublicCategoryOut]
