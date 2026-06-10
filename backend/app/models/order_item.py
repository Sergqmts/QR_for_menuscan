import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, Numeric, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (Index("idx_order_items_order_id", "order_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    dish_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dishes.id"), nullable=False)
    guest_id: Mapped[str] = mapped_column(String(100), nullable=False)
    guest_name: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
