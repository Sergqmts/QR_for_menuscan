import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.order import OrderCreate


async def create_order(db: AsyncSession, data: OrderCreate) -> Order:
    from app.models.dish import Dish

    # Resolve prices from DB — never trust client-supplied unit_price
    order_items_data = []
    total = Decimal(0)
    for item_data in data.items:
        dish_result = await db.execute(
            select(Dish).where(Dish.id == item_data.dish_id, Dish.venue_id == data.venue_id)
        )
        dish = dish_result.scalar_one_or_none()
        if not dish:
            raise HTTPException(
                status_code=400,
                detail=f"Dish {item_data.dish_id} not found in venue",
            )
        server_price = dish.price
        total += server_price * item_data.quantity
        order_items_data.append((item_data, server_price))

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
    for item_data, server_price in order_items_data:
        db.add(OrderItem(
            id=uuid.uuid4(),
            order_id=order.id,
            dish_id=item_data.dish_id,
            guest_id=item_data.guest_id,
            guest_name=item_data.guest_name,
            quantity=item_data.quantity,
            unit_price=server_price,  # server-derived, not client-supplied
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
