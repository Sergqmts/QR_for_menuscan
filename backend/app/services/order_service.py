import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.order import OrderCreate


async def create_order(db: AsyncSession, data: OrderCreate) -> Order:
    total = sum(item.unit_price * item.quantity for item in data.items)
    order = Order(
        id=uuid.uuid4(),
        venue_id=data.venue_id,
        table_id=data.table_id,
        session_id=data.session_id,
        status="accepted",
        total_amount=total,
        comment=data.comment,
    )
    db.add(order)
    await db.flush()
    for item_data in data.items:
        db.add(OrderItem(
            id=uuid.uuid4(),
            order_id=order.id,
            dish_id=item_data.dish_id,
            guest_id=item_data.guest_id,
            guest_name=item_data.guest_name,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            comment=item_data.comment,
        ))
    await db.commit()
    await db.refresh(order)
    return order


async def get_order_with_items(db: AsyncSession, order_id: uuid.UUID) -> Order:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    order.__dict__["items"] = items_result.scalars().all()
    return order


async def update_order_status(db: AsyncSession, order_id: uuid.UUID, status: str) -> Order:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = status
    await db.commit()
    await db.refresh(order)
    return order
