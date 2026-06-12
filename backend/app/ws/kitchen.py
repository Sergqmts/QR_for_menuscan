import asyncio
import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import decode_access_token
from app.models.venue import Venue
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.user import User


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _msg(type_: str, payload: dict) -> str:
    return json.dumps({"type": type_, "payload": payload, "timestamp": _now()})


_HANDOFF_PREFIX = "kitchen_handoff:"


async def _resolve_token(token: str, code: str, redis: aioredis.Redis) -> str:
    """Return the JWT to use, resolving a handoff code if provided.
    Codes are single-use: the key is deleted atomically on first read."""
    if token:
        return token
    if code:
        key = f"{_HANDOFF_PREFIX}{code}"
        resolved = await redis.getdel(key)  # atomic get-and-delete (Redis ≥ 6.2)
        return resolved or ""
    return ""


async def ws_kitchen_handler(
    websocket: WebSocket,
    venue_id: uuid.UUID,
    token: str,
    db: AsyncSession,
    code: str = "",
):
    await websocket.accept()

    auth_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    resolved_token = await _resolve_token(token, code, auth_redis)
    await auth_redis.aclose()

    # Verify token and ownership
    user_id_str = decode_access_token(resolved_token)
    if not user_id_str:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_result = await db.execute(select(User).where(User.id == uuid.UUID(user_id_str)))
    user = user_result.scalar_one_or_none()
    if not user:
        await websocket.close(code=4001, reason="User not found")
        return

    venue_result = await db.execute(
        select(Venue).where(Venue.id == venue_id, Venue.owner_id == user.id)
    )
    venue = venue_result.scalar_one_or_none()
    if not venue:
        await websocket.close(code=4003, reason="Venue not found or not authorized")
        return

    pub_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    sub_redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    kitchen_channel = f"kitchen:{venue_id}"
    pubsub = sub_redis.pubsub()
    await pubsub.subscribe(kitchen_channel)

    # Send active orders on connect
    orders_result = await db.execute(
        select(Order)
        .where(Order.venue_id == venue_id, Order.status.in_(["accepted", "cooking", "ready"]))
        .order_by(Order.created_at)
    )
    active_orders = orders_result.scalars().all()
    orders_out = []
    for order in active_orders:
        items_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        items = items_result.scalars().all()
        from app.models.table import Table
        table_result = await db.execute(select(Table).where(Table.id == order.table_id))
        table = table_result.scalar_one_or_none()
        orders_out.append({
            "order_id": str(order.id),
            "table": {"number": table.number if table else 0, "label": table.label if table else ""},
            "status": order.status,
            "total_amount": float(order.total_amount),
            "created_at": order.created_at.isoformat(),
            "items": [
                {
                    "dish_name": "",
                    "quantity": i.quantity,
                    "comment": i.comment or "",
                    "guest_name": i.guest_name or "",
                }
                for i in items
            ],
        })

    await websocket.send_text(_msg("kitchen_connected", {"active_orders": orders_out}))

    async def forward_pubsub():
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"])
        except Exception:
            pass

    forward_task = asyncio.create_task(forward_pubsub())

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            event_type = data.get("type")
            payload = data.get("payload", {})

            if event_type == "update_order_status":
                order_id = uuid.UUID(payload["order_id"])
                new_status = payload["status"]
                order_result = await db.execute(select(Order).where(Order.id == order_id))
                order = order_result.scalar_one_or_none()
                if order and order.venue_id == venue_id:
                    order.status = new_status
                    await db.commit()
                    # Broadcast to kitchen
                    await pub_redis.publish(
                        kitchen_channel,
                        _msg("order_status_updated", {"order_id": str(order_id), "status": new_status}),
                    )
                    # Notify table guests
                    table_channel = f"table:{order.table_id}"
                    await pub_redis.publish(
                        table_channel,
                        _msg("order_status_changed", {
                            "order_id": str(order_id),
                            "status": new_status,
                            "updated_at": _now(),
                        }),
                    )

            if event_type == "ping":
                await websocket.send_text(_msg("pong", {}))

    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        try:
            await pubsub.unsubscribe(kitchen_channel)
        except Exception:
            pass
        try:
            await sub_redis.aclose()
        except Exception:
            pass
        try:
            await pub_redis.aclose()
        except Exception:
            pass
