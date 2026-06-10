import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.order import OrderCreate, OrderOut, OrderItemOut, OrderStatusUpdate
from app.services.order_service import create_order, get_order_with_items, update_order_status
from app.services.venue_service import get_venue_or_404

router = APIRouter(tags=["orders"])


@router.post("/orders", response_model=OrderOut, status_code=201)
async def post_order(data: OrderCreate, db: AsyncSession = Depends(get_db)):
    order = await create_order(db, data)
    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    order.__dict__["items"] = items_result.scalars().all()
    return OrderOut.model_validate(order)


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
async def patch_order_status(
    order_id: uuid.UUID,
    data: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = await get_order_with_items(db, order_id)
    await get_venue_or_404(db, order.venue_id, user.id)
    order = await update_order_status(db, order_id, data.status)
    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    order.__dict__["items"] = items_result.scalars().all()
    return OrderOut.model_validate(order)


@router.get("/venues/{venue_id}/orders", response_model=dict)
async def list_orders(
    venue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(
        select(Order)
        .where(Order.venue_id == venue_id)
        .order_by(Order.created_at.desc())
        .limit(100)
    )
    orders = result.scalars().all()
    out = []
    for order in orders:
        items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        order.__dict__["items"] = items_result.scalars().all()
        out.append(OrderOut.model_validate(order))
    return {"orders": out}
