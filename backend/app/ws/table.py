import asyncio
import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.table import Table
from app.models.venue import Venue
from app.services.table_session import TableSessionService
from app.services.order_service import create_order
from app.schemas.order import OrderCreate, OrderItemCreate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _msg(type_: str, payload: dict) -> str:
    return json.dumps({"type": type_, "payload": payload, "timestamp": _now()})


async def ws_table_handler(
    websocket: WebSocket,
    table_id: uuid.UUID,
    guest_id: str,
    venue_id: str,
    db: AsyncSession,
):
    await websocket.accept()

    table_result = await db.execute(select(Table).where(Table.id == table_id))
    table = table_result.scalar_one_or_none()
    if not table:
        await websocket.close(code=4004, reason="Table not found")
        return

    venue_result = await db.execute(select(Venue).where(Venue.id == table.venue_id))
    venue = venue_result.scalar_one_or_none()
    if not venue:
        await websocket.close(code=4004, reason="Venue not found")
        return

    pub_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    sub_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    svc = TableSessionService(pub_redis)

    table_channel = f"table:{table_id}"
    venue_id_str = str(table.venue_id)
    connection_id = str(uuid.uuid4())

    pubsub = sub_redis.pubsub()
    await pubsub.subscribe(table_channel)

    await svc.get_or_create(venue_id_str, str(table_id))

    async def forward_pubsub():
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    if data.get("_sender") == connection_id:
                        continue
                    data.pop("_sender", None)
                    await websocket.send_text(json.dumps(data))
        except Exception:
            pass

    forward_task = asyncio.create_task(forward_pubsub())

    async def publish(type_: str, payload: dict):
        msg = {"type": type_, "payload": payload, "timestamp": _now(), "_sender": connection_id}
        await pub_redis.publish(table_channel, json.dumps(msg))

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            event_type = data.get("type")
            payload = data.get("payload", {})

            if event_type == "ping":
                await websocket.send_text(_msg("pong", {}))
                continue

            if event_type == "guest_join":
                gid = payload.get("guest_id", guest_id)
                gname = payload.get("guest_name", "Гость")
                await svc.add_guest(venue_id_str, str(table_id), gid, gname)
                session = await svc.get_session(venue_id_str, str(table_id))
                await websocket.send_text(_msg("table_joined", {
                    "session_id": session["session_id"],
                    "table": {"id": str(table.id), "number": table.number, "label": table.label},
                    "guests": session["guests"],
                    "cart": session["cart"],
                    "total": session["total"],
                }))
                await publish("guest_connected", {"guest_id": gid, "guest_name": gname})
                continue

            if event_type == "add_item":
                cart_item_id = payload.get("cart_item_id") or str(uuid.uuid4())
                item = {
                    "cart_item_id": cart_item_id,
                    "dish_id": payload["dish_id"],
                    "dish_name": payload["dish_name"],
                    "unit_price": float(payload["unit_price"]),
                    "quantity": int(payload.get("quantity", 1)),
                    "comment": payload.get("comment", ""),
                    "guest_id": payload["guest_id"],
                    "guest_name": payload.get("guest_name", ""),
                }
                result = await svc.add_cart_item(venue_id_str, str(table_id), item)
                cart_updated_msg = _msg("cart_updated", {
                    "action": "add",
                    "cart_item": item,
                    "cart": result["cart"],
                    "total": result["total"],
                })
                # Send directly to initiating connection (works in test env without pub/sub relay)
                await websocket.send_text(cart_updated_msg)
                # Also publish for other connected clients
                await pub_redis.publish(table_channel, cart_updated_msg)
                continue

            if event_type == "remove_item":
                result = await svc.remove_cart_item(
                    venue_id_str, str(table_id),
                    payload["cart_item_id"],
                    payload["guest_id"],
                )
                cart_updated_msg = _msg("cart_updated", {
                    "action": "remove",
                    "cart_item": {"cart_item_id": payload["cart_item_id"]},
                    "cart": result["cart"],
                    "total": result["total"],
                })
                await websocket.send_text(cart_updated_msg)
                await pub_redis.publish(table_channel, cart_updated_msg)
                continue

            if event_type == "update_qty":
                result = await svc.update_cart_qty(
                    venue_id_str, str(table_id),
                    payload["cart_item_id"],
                    int(payload["quantity"]),
                    payload["guest_id"],
                )
                cart_updated_msg = _msg("cart_updated", {
                    "action": "update",
                    "cart_item": {"cart_item_id": payload["cart_item_id"], "quantity": payload["quantity"]},
                    "cart": result["cart"],
                    "total": result["total"],
                })
                await websocket.send_text(cart_updated_msg)
                await pub_redis.publish(table_channel, cart_updated_msg)
                continue

            if event_type == "submit_order":
                current_session = await svc.get_session(venue_id_str, str(table_id))
                cart = current_session["cart"] if current_session else []
                if not cart:
                    await websocket.send_text(_msg("error", {"code": "CART_EMPTY", "message": "Корзина пуста"}))
                    continue
                order_data = OrderCreate(
                    venue_id=table.venue_id,
                    table_id=table.id,
                    session_id=current_session["session_id"],
                    comment=payload.get("table_comment"),
                    items=[
                        OrderItemCreate(
                            dish_id=uuid.UUID(i["dish_id"]),
                            guest_id=i["guest_id"],
                            guest_name=i.get("guest_name"),
                            quantity=i["quantity"],
                            unit_price=i["unit_price"],
                            comment=i.get("comment"),
                        )
                        for i in cart
                    ],
                )
                order = await create_order(db, order_data)
                await svc.clear_cart(venue_id_str, str(table_id))
                order_payload = {
                    "order_id": str(order.id),
                    "status": order.status,
                    "total_amount": float(order.total_amount),
                    "created_at": order.created_at.isoformat(),
                }
                await publish("order_confirmed", order_payload)
                kitchen_channel = f"kitchen:{table.venue_id}"
                kitchen_order = {
                    "order_id": str(order.id),
                    "table": {"number": table.number, "label": table.label},
                    "status": "accepted",
                    "total_amount": float(order.total_amount),
                    "created_at": order.created_at.isoformat(),
                    "items": [
                        {
                            "dish_name": i["dish_name"],
                            "quantity": i["quantity"],
                            "comment": i.get("comment", ""),
                            "guest_name": i.get("guest_name", ""),
                        }
                        for i in cart
                    ],
                }
                await pub_redis.publish(kitchen_channel, _msg("new_order", kitchen_order))
                continue

            if event_type == "call_waiter":
                await publish("waiter_called", {"table_id": str(table_id), "table_number": table.number})
                continue

    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        try:
            await pubsub.unsubscribe(table_channel)
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
