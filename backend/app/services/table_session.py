import json
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

SESSION_TTL = 14400  # 4 hours


class TableSessionService:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    def _key(self, venue_id: str, table_id: str) -> str:
        return f"table_session:{venue_id}:{table_id}"

    def _compute_total(self, cart: list[dict]) -> float:
        return sum(item["unit_price"] * item["quantity"] for item in cart)

    async def get_or_create(self, venue_id: str, table_id: str) -> dict:
        key = self._key(venue_id, table_id)
        existing = await self.redis.hgetall(key)
        if existing:
            await self.redis.expire(key, SESSION_TTL)
            return {
                "session_id": existing["session_id"],
                "guests": json.loads(existing.get("guests", "[]")),
                "cart": json.loads(existing.get("cart", "[]")),
                "total": self._compute_total(json.loads(existing.get("cart", "[]"))),
            }
        session_id = str(uuid.uuid4())
        await self.redis.hset(key, mapping={
            "session_id": session_id,
            "guests": "[]",
            "cart": "[]",
            "last_activity": datetime.now(timezone.utc).isoformat(),
        })
        await self.redis.expire(key, SESSION_TTL)
        return {"session_id": session_id, "guests": [], "cart": [], "total": 0.0}

    async def get_session(self, venue_id: str, table_id: str) -> dict | None:
        key = self._key(venue_id, table_id)
        data = await self.redis.hgetall(key)
        if not data:
            return None
        cart = json.loads(data.get("cart", "[]"))
        return {
            "session_id": data["session_id"],
            "guests": json.loads(data.get("guests", "[]")),
            "cart": cart,
            "total": self._compute_total(cart),
        }

    async def add_guest(self, venue_id: str, table_id: str, guest_id: str, guest_name: str) -> None:
        key = self._key(venue_id, table_id)
        raw = await self.redis.hget(key, "guests")
        guests: list = json.loads(raw or "[]")
        if not any(g["guest_id"] == guest_id for g in guests):
            guests.append({"guest_id": guest_id, "guest_name": guest_name})
        await self.redis.hset(key, "guests", json.dumps(guests))
        await self.redis.expire(key, SESSION_TTL)

    async def remove_guest(self, venue_id: str, table_id: str, guest_id: str) -> None:
        key = self._key(venue_id, table_id)
        raw = await self.redis.hget(key, "guests")
        guests = [g for g in json.loads(raw or "[]") if g["guest_id"] != guest_id]
        await self.redis.hset(key, "guests", json.dumps(guests))

    async def add_cart_item(self, venue_id: str, table_id: str, item: dict) -> dict:
        key = self._key(venue_id, table_id)
        raw = await self.redis.hget(key, "cart")
        cart: list = json.loads(raw or "[]")
        cart.append(item)
        await self.redis.hset(key, "cart", json.dumps(cart))
        await self.redis.expire(key, SESSION_TTL)
        return {"cart": cart, "total": self._compute_total(cart)}

    async def remove_cart_item(
        self, venue_id: str, table_id: str, cart_item_id: str, guest_id: str
    ) -> dict:
        key = self._key(venue_id, table_id)
        raw = await self.redis.hget(key, "cart")
        cart = [
            i for i in json.loads(raw or "[]")
            if not (i["cart_item_id"] == cart_item_id and i["guest_id"] == guest_id)
        ]
        await self.redis.hset(key, "cart", json.dumps(cart))
        return {"cart": cart, "total": self._compute_total(cart)}

    async def update_cart_qty(
        self, venue_id: str, table_id: str, cart_item_id: str, quantity: int, guest_id: str
    ) -> dict:
        key = self._key(venue_id, table_id)
        raw = await self.redis.hget(key, "cart")
        cart = json.loads(raw or "[]")
        for item in cart:
            if item["cart_item_id"] == cart_item_id and item["guest_id"] == guest_id:
                item["quantity"] = quantity
                break
        await self.redis.hset(key, "cart", json.dumps(cart))
        return {"cart": cart, "total": self._compute_total(cart)}

    async def clear_cart(self, venue_id: str, table_id: str) -> dict:
        key = self._key(venue_id, table_id)
        await self.redis.hset(key, "cart", "[]")
        return {"cart": [], "total": 0.0}
