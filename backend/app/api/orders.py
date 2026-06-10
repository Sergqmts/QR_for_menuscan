import uuid
import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.order import OrderCreate, OrderOut, OrderStatusUpdate
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


@router.get("/venues/{venue_id}/orders")
async def list_orders(
    venue_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    format: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, user.id)
    stmt = select(Order).where(Order.venue_id == venue_id)
    if status:
        stmt = stmt.where(Order.status == status)
    stmt = stmt.order_by(Order.created_at.desc())

    if format == "csv":
        result = await db.execute(stmt)
        orders = result.scalars().all()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "created_at", "table_id", "status", "total_amount", "session_id"])
        for order in orders:
            writer.writerow([str(order.id), order.created_at.isoformat(), str(order.table_id), order.status, str(order.total_amount), order.session_id])
        buf.seek(0)
        return StreamingResponse(
            io.BytesIO(buf.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=orders_{venue_id}.csv"},
        )

    count_stmt = select(func.count(Order.id)).where(Order.venue_id == venue_id)
    if status:
        count_stmt = count_stmt.where(Order.status == status)
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * limit
    result = await db.execute(stmt.offset(offset).limit(limit))
    orders = result.scalars().all()

    out = []
    for order in orders:
        items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        order.__dict__["items"] = items_result.scalars().all()
        out.append(OrderOut.model_validate(order))
    return {"orders": out, "page": page, "limit": limit, "total": total}
