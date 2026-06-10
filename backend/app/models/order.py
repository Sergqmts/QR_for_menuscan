import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Text, ForeignKey, DateTime, Numeric, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("idx_orders_venue_id", "venue_id"),
        Index("idx_orders_table_id", "table_id"),
        Index("idx_orders_status", "status"),
        Index("idx_orders_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tables.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="accepted")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
