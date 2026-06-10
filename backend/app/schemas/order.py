from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


ORDER_STATUSES = {"accepted", "cooking", "ready", "served", "cancelled"}


class OrderItemCreate(BaseModel):
    dish_id: uuid.UUID
    guest_id: str
    guest_name: str | None = None
    quantity: int = Field(default=1, ge=1, le=100)
    unit_price: Decimal = Field(ge=Decimal('0.01'))
    comment: str | None = None


class OrderCreate(BaseModel):
    venue_id: uuid.UUID
    table_id: uuid.UUID
    session_id: str
    comment: str | None = None
    items: list[OrderItemCreate]


class OrderStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ORDER_STATUSES:
            raise ValueError(f"status must be one of {ORDER_STATUSES}")
        return v


class OrderItemOut(BaseModel):
    id: uuid.UUID
    dish_id: uuid.UUID
    guest_id: str
    guest_name: str | None
    quantity: int
    unit_price: Decimal
    comment: str | None

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: uuid.UUID
    venue_id: uuid.UUID
    table_id: uuid.UUID
    session_id: str
    status: str
    total_amount: Decimal
    comment: str | None
    created_at: datetime
    items: list[OrderItemOut] = []

    model_config = {"from_attributes": True}


class PublicTableOut(BaseModel):
    id: uuid.UUID
    number: int
    label: str | None

    model_config = {"from_attributes": True}
