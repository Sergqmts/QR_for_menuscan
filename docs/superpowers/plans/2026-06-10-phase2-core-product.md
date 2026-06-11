# MenuScan Phase 2 — Core Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the guest-facing menu PWA and kitchen display connected via WebSocket with a shared table cart backed by Redis Pub/Sub, plus the full orders lifecycle (submit → kitchen → status back to guest).

**Architecture:** FastAPI WebSocket handlers subscribe to Redis Pub/Sub channels (`table:{table_id}`, `kitchen:{venue_id}`). Cart state lives in a Redis Hash keyed `table_session:{venue_id}:{table_id}` with TTL 4h. On `submit_order`, cart items are persisted to PostgreSQL with prices locked at submission time and the cart is cleared. Kitchen screen receives new orders via WS; status updates propagate back to guests. Frontend: two standalone Next.js 14 apps — `frontend/apps/guest` (PWA) and `frontend/apps/kitchen`.

**Tech Stack:** Python: FastAPI WebSocket, `redis[hiredis]` (async), pytest-asyncio, starlette TestClient. Frontend: Next.js 14 (App Router), TypeScript, Tailwind CSS, Zustand, native WebSocket API.

---

## File Map

```
backend/
├── app/
│   ├── models/
│   │   ├── order.py              # CREATE — Order model
│   │   ├── order_item.py         # CREATE — OrderItem model
│   │   └── __init__.py           # MODIFY — add Order, OrderItem
│   ├── core/
│   │   └── redis.py              # CREATE — async Redis client factory
│   ├── services/
│   │   ├── table_session.py      # CREATE — Redis cart CRUD service
│   │   └── order_service.py      # CREATE — create_order, update_status
│   ├── schemas/
│   │   └── order.py              # CREATE — Pydantic schemas for orders
│   ├── api/
│   │   ├── orders.py             # CREATE — REST: POST /orders, PATCH status, GET list
│   │   └── menu.py               # MODIFY — add GET /menu/{slug}/table/{number}
│   ├── ws/
│   │   ├── __init__.py           # CREATE — empty
│   │   ├── table.py              # CREATE — /ws/table/{table_id}
│   │   └── kitchen.py            # CREATE — /ws/kitchen/{venue_id}
│   └── main.py                   # MODIFY — add orders router + WS routes
├── alembic/versions/
│   └── xxxx_add_orders.py        # CREATE — via autogenerate
└── tests/
    ├── conftest.py               # MODIFY — add Redis test fixtures
    ├── test_table_session.py     # CREATE — Redis session unit tests
    ├── test_orders.py            # CREATE — REST order endpoint tests
    └── test_ws_table.py          # CREATE — WebSocket smoke tests

frontend/
├── apps/
│   ├── guest/                    # CREATE — Next.js 14 PWA
│   │   ├── package.json
│   │   ├── next.config.js
│   │   ├── tailwind.config.js
│   │   ├── tsconfig.json
│   │   ├── public/
│   │   │   └── manifest.json     # PWA manifest
│   │   └── app/
│   │       ├── layout.tsx
│   │       ├── globals.css
│   │       ├── [slug]/
│   │       │   └── table/
│   │       │       └── [tableNumber]/
│   │       │           └── page.tsx   # Menu page
│   │       └── components/
│   │           ├── DishCard.tsx
│   │           ├── CategoryTabs.tsx
│   │           ├── CartDrawer.tsx
│   │           └── GuestNameModal.tsx
│   │   └── lib/
│   │       ├── api.ts                 # fetch wrappers
│   │       ├── cartStore.ts           # Zustand cart state
│   │       └── useTableWebSocket.ts   # WS hook
│   └── kitchen/                  # CREATE — Next.js 14 kitchen display
│       ├── package.json
│       ├── next.config.js
│       ├── tailwind.config.js
│       ├── tsconfig.json
│       └── app/
│           ├── layout.tsx
│           ├── globals.css
│           ├── [venueId]/
│           │   └── page.tsx           # Kitchen display
│           └── components/
│               └── OrderCard.tsx
│           └── lib/
│               └── useKitchenWebSocket.ts
```

---

## Task 1: Order + OrderItem Models + Alembic Migration

**Files:**
- Create: `backend/app/models/order.py`
- Create: `backend/app/models/order_item.py`
- Modify: `backend/app/models/__init__.py`
- Run: alembic autogenerate migration

- [ ] **Step 1: Create backend/app/models/order.py**

```python
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
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id"), nullable=False)
    table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tables.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="accepted")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Create backend/app/models/order_item.py**

```python
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
```

- [ ] **Step 3: Update backend/app/models/__init__.py**

```python
from app.models.user import User
from app.models.venue import Venue
from app.models.table import Table
from app.models.category import Category
from app.models.dish import Dish
from app.models.parse_job import ParseJob
from app.models.qr_batch import QRBatch
from app.models.order import Order
from app.models.order_item import OrderItem

__all__ = ["User", "Venue", "Table", "Category", "Dish", "ParseJob", "QRBatch", "Order", "OrderItem"]
```

- [ ] **Step 4: Generate and apply migration**

```bash
cd backend
alembic revision --autogenerate -m "add_orders"
alembic upgrade head
```

Verify:
```bash
docker compose exec db psql -U menuscan -c "\dt"
```

Expected: `orders` and `order_items` tables now listed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/order.py backend/app/models/order_item.py backend/app/models/__init__.py backend/alembic/
git commit -m "feat: Order + OrderItem models + migration"
```

---

## Task 2: Redis Client + Table Session Service

**Files:**
- Create: `backend/app/core/redis.py`
- Create: `backend/app/services/table_session.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_table_session.py`

- [ ] **Step 1: Create backend/app/core/redis.py**

```python
import redis.asyncio as aioredis
from app.core.config import settings

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
```

- [ ] **Step 2: Write failing tests for table_session**

Create `backend/tests/test_table_session.py`:

```python
import pytest
import uuid
import redis.asyncio as aioredis


TEST_REDIS_URL = "redis://localhost:6379/1"


@pytest.fixture
async def redis_client():
    client = aioredis.from_url(TEST_REDIS_URL, decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def venue_id():
    return str(uuid.uuid4())


@pytest.fixture
def table_id():
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_get_or_create_new_session(redis_client, venue_id, table_id):
    from app.services.table_session import TableSessionService
    svc = TableSessionService(redis_client)
    session = await svc.get_or_create(venue_id, table_id)
    assert "session_id" in session
    assert session["cart"] == []
    assert session["guests"] == []


@pytest.mark.asyncio
async def test_get_existing_session_returns_same_id(redis_client, venue_id, table_id):
    from app.services.table_session import TableSessionService
    svc = TableSessionService(redis_client)
    s1 = await svc.get_or_create(venue_id, table_id)
    s2 = await svc.get_or_create(venue_id, table_id)
    assert s1["session_id"] == s2["session_id"]


@pytest.mark.asyncio
async def test_add_and_remove_guest(redis_client, venue_id, table_id):
    from app.services.table_session import TableSessionService
    svc = TableSessionService(redis_client)
    await svc.get_or_create(venue_id, table_id)
    guest_id = str(uuid.uuid4())
    await svc.add_guest(venue_id, table_id, guest_id, "Алексей")
    session = await svc.get_session(venue_id, table_id)
    assert any(g["guest_id"] == guest_id for g in session["guests"])
    await svc.remove_guest(venue_id, table_id, guest_id)
    session = await svc.get_session(venue_id, table_id)
    assert not any(g["guest_id"] == guest_id for g in session["guests"])


@pytest.mark.asyncio
async def test_add_cart_item(redis_client, venue_id, table_id):
    from app.services.table_session import TableSessionService
    svc = TableSessionService(redis_client)
    await svc.get_or_create(venue_id, table_id)
    item = {
        "cart_item_id": str(uuid.uuid4()),
        "dish_id": str(uuid.uuid4()),
        "dish_name": "Борщ",
        "unit_price": 350.0,
        "quantity": 1,
        "comment": "",
        "guest_id": str(uuid.uuid4()),
        "guest_name": "Мария",
    }
    session = await svc.add_cart_item(venue_id, table_id, item)
    assert len(session["cart"]) == 1
    assert session["cart"][0]["dish_name"] == "Борщ"
    assert abs(session["total"] - 350.0) < 0.01


@pytest.mark.asyncio
async def test_remove_cart_item(redis_client, venue_id, table_id):
    from app.services.table_session import TableSessionService
    svc = TableSessionService(redis_client)
    await svc.get_or_create(venue_id, table_id)
    guest_id = str(uuid.uuid4())
    cart_item_id = str(uuid.uuid4())
    item = {
        "cart_item_id": cart_item_id,
        "dish_id": str(uuid.uuid4()),
        "dish_name": "Котлета",
        "unit_price": 420.0,
        "quantity": 2,
        "comment": "",
        "guest_id": guest_id,
        "guest_name": "Иван",
    }
    await svc.add_cart_item(venue_id, table_id, item)
    session = await svc.remove_cart_item(venue_id, table_id, cart_item_id, guest_id)
    assert session["cart"] == []


@pytest.mark.asyncio
async def test_update_cart_qty(redis_client, venue_id, table_id):
    from app.services.table_session import TableSessionService
    svc = TableSessionService(redis_client)
    await svc.get_or_create(venue_id, table_id)
    guest_id = str(uuid.uuid4())
    cart_item_id = str(uuid.uuid4())
    item = {
        "cart_item_id": cart_item_id,
        "dish_id": str(uuid.uuid4()),
        "dish_name": "Чай",
        "unit_price": 100.0,
        "quantity": 1,
        "comment": "",
        "guest_id": guest_id,
        "guest_name": "Ольга",
    }
    await svc.add_cart_item(venue_id, table_id, item)
    session = await svc.update_cart_qty(venue_id, table_id, cart_item_id, 3, guest_id)
    assert session["cart"][0]["quantity"] == 3
    assert abs(session["total"] - 300.0) < 0.01


@pytest.mark.asyncio
async def test_clear_cart(redis_client, venue_id, table_id):
    from app.services.table_session import TableSessionService
    svc = TableSessionService(redis_client)
    await svc.get_or_create(venue_id, table_id)
    item = {
        "cart_item_id": str(uuid.uuid4()),
        "dish_id": str(uuid.uuid4()),
        "dish_name": "Блин",
        "unit_price": 80.0,
        "quantity": 1,
        "comment": "",
        "guest_id": str(uuid.uuid4()),
        "guest_name": "Тест",
    }
    await svc.add_cart_item(venue_id, table_id, item)
    session = await svc.clear_cart(venue_id, table_id)
    assert session["cart"] == []
    assert session["total"] == 0.0
```

- [ ] **Step 3: Run tests — expect FAIL**

```bash
cd backend && python3 -m pytest tests/test_table_session.py -v
```

Expected: `ImportError` — `table_session` module doesn't exist yet.

- [ ] **Step 4: Create backend/app/services/table_session.py**

```python
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
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
cd backend && python3 -m pytest tests/test_table_session.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/redis.py backend/app/services/table_session.py backend/tests/test_table_session.py
git commit -m "feat: Redis client + table session cart service"
```

---

## Task 3: Orders REST API + Public Table Lookup

**Files:**
- Create: `backend/app/schemas/order.py`
- Create: `backend/app/services/order_service.py`
- Create: `backend/app/api/orders.py`
- Modify: `backend/app/api/menu.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_orders.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_orders.py`:

```python
import pytest
import uuid as uuid_mod


async def _setup(client):
    email = f"o_{uuid_mod.uuid4().hex[:6]}@test.ru"
    r = await client.post("/auth/register", json={"email": email, "password": "Pass123", "full_name": "O"})
    token = r.json()["access_token"]
    vr = await client.post(
        "/venues",
        json={"name": f"V{uuid_mod.uuid4().hex[:4]}", "table_count": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    venue = vr.json()["venue"]
    tr = await client.get(
        f"/venues/{venue['id']}/tables",
        headers={"Authorization": f"Bearer {token}"},
    )
    table = tr.json()["tables"][0]
    cr = await client.post(
        f"/venues/{venue['id']}/categories",
        json={"name": "Горячее", "slug": "hot"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cr.json()["id"]
    dr = await client.post(
        f"/venues/{venue['id']}/dishes",
        json={"category_id": cat_id, "name": "Борщ", "price": 350.00},
        headers={"Authorization": f"Bearer {token}"},
    )
    dish = dr.json()
    return token, venue, table, dish


@pytest.mark.asyncio
async def test_create_order(client):
    token, venue, table, dish = await _setup(client)
    guest_id = str(uuid_mod.uuid4())
    r = await client.post(
        "/orders",
        json={
            "venue_id": venue["id"],
            "table_id": table["id"],
            "session_id": "test-session-123",
            "comment": "без лука",
            "items": [
                {
                    "dish_id": dish["id"],
                    "guest_id": guest_id,
                    "guest_name": "Алексей",
                    "quantity": 2,
                    "unit_price": 350.00,
                    "comment": "",
                }
            ],
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "accepted"
    assert abs(float(data["total_amount"]) - 700.0) < 0.01
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_update_order_status(client):
    token, venue, table, dish = await _setup(client)
    guest_id = str(uuid_mod.uuid4())
    cr = await client.post(
        "/orders",
        json={
            "venue_id": venue["id"],
            "table_id": table["id"],
            "session_id": "sess-abc",
            "items": [
                {
                    "dish_id": dish["id"],
                    "guest_id": guest_id,
                    "guest_name": "Тест",
                    "quantity": 1,
                    "unit_price": 350.00,
                    "comment": "",
                }
            ],
        },
    )
    order_id = cr.json()["id"]
    r = await client.patch(
        f"/orders/{order_id}/status",
        json={"status": "cooking"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cooking"


@pytest.mark.asyncio
async def test_update_order_status_invalid(client):
    token, venue, table, dish = await _setup(client)
    cr = await client.post(
        "/orders",
        json={
            "venue_id": venue["id"],
            "table_id": table["id"],
            "session_id": "sess-xyz",
            "items": [
                {
                    "dish_id": dish["id"],
                    "guest_id": str(uuid_mod.uuid4()),
                    "guest_name": "X",
                    "quantity": 1,
                    "unit_price": 350.00,
                    "comment": "",
                }
            ],
        },
    )
    order_id = cr.json()["id"]
    r = await client.patch(
        f"/orders/{order_id}/status",
        json={"status": "invalid_status"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_venue_orders(client):
    token, venue, table, dish = await _setup(client)
    await client.post(
        "/orders",
        json={
            "venue_id": venue["id"],
            "table_id": table["id"],
            "session_id": "sess-list",
            "items": [
                {
                    "dish_id": dish["id"],
                    "guest_id": str(uuid_mod.uuid4()),
                    "guest_name": "L",
                    "quantity": 1,
                    "unit_price": 350.00,
                    "comment": "",
                }
            ],
        },
    )
    r = await client.get(
        f"/venues/{venue['id']}/orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["orders"]) >= 1


@pytest.mark.asyncio
async def test_public_table_lookup(client):
    token, venue, table, dish = await _setup(client)
    r = await client.get(f"/menu/{venue['slug']}/table/1")
    assert r.status_code == 200
    data = r.json()
    assert data["number"] == 1
    assert "id" in data
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && python3 -m pytest tests/test_orders.py -v
```

Expected: All FAIL (404 or ImportError).

- [ ] **Step 3: Create backend/app/schemas/order.py**

```python
from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, field_validator


ORDER_STATUSES = {"accepted", "cooking", "ready", "served", "cancelled"}


class OrderItemCreate(BaseModel):
    dish_id: uuid.UUID
    guest_id: str
    guest_name: str | None = None
    quantity: int = 1
    unit_price: Decimal
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
```

- [ ] **Step 4: Create backend/app/services/order_service.py**

```python
import uuid
from decimal import Decimal
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
```

- [ ] **Step 5: Create backend/app/api/orders.py**

```python
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
```

- [ ] **Step 6: Add public table lookup to backend/app/api/menu.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid as uuid_mod

from app.core.database import get_db
from app.schemas.menu import PublicMenuOut
from app.schemas.order import PublicTableOut
from app.services.menu_service import get_public_menu
from app.models.venue import Venue
from app.models.table import Table

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("/{venue_slug}", response_model=PublicMenuOut)
async def get_menu(venue_slug: str, db: AsyncSession = Depends(get_db)):
    return await get_public_menu(db, venue_slug)


@router.get("/{venue_slug}/table/{table_number}", response_model=PublicTableOut)
async def get_table_by_number(
    venue_slug: str, table_number: int, db: AsyncSession = Depends(get_db)
):
    venue_result = await db.execute(
        select(Venue).where(Venue.slug == venue_slug, Venue.is_active == True)
    )
    venue = venue_result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    table_result = await db.execute(
        select(Table).where(Table.venue_id == venue.id, Table.number == table_number)
    )
    table = table_result.scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    return PublicTableOut.model_validate(table)
```

- [ ] **Step 7: Update backend/app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.venues import router as venues_router
from app.api.tables import router as tables_router
from app.api.categories import router as categories_router
from app.api.dishes import router as dishes_router
from app.api.menu import router as menu_router
from app.api.parse import router as parse_router
from app.api.qr import router as qr_router
from app.api.orders import router as orders_router

app = FastAPI(title="MenuScan API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(venues_router)
app.include_router(tables_router)
app.include_router(categories_router)
app.include_router(dishes_router)
app.include_router(menu_router)
app.include_router(parse_router)
app.include_router(qr_router)
app.include_router(orders_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Run tests**

```bash
cd backend && python3 -m pytest tests/test_orders.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 9: Run full suite to check no regressions**

```bash
cd backend && python3 -m pytest tests/ -v --tb=short
```

Expected: All 33 tests PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/app/schemas/order.py backend/app/services/order_service.py backend/app/api/orders.py backend/app/api/menu.py backend/app/main.py backend/tests/test_orders.py
git commit -m "feat: orders REST API + public table lookup endpoint"
```

---

## Task 4: Table WebSocket Handler

**Files:**
- Create: `backend/app/ws/__init__.py`
- Create: `backend/app/ws/table.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_ws_table.py`

- [ ] **Step 1: Write failing WebSocket smoke test**

Create `backend/tests/test_ws_table.py`:

```python
import pytest
import uuid
import asyncio
from starlette.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.core.database import get_db
from app.models.base import Base
from app.models.user import User
from app.models.venue import Venue
from app.models.table import Table
from app.core.security import hash_password

TEST_DB_URL = "postgresql+asyncpg://menuscan:menuscan@localhost:5432/menuscan_test"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def ws_venue_table():
    """Create venue + table in test DB, return (venue_id_str, table_id_str)."""
    async def _create():
        async with _SessionLocal() as db:
            user = User(
                id=uuid.uuid4(),
                email=f"ws_{uuid.uuid4().hex[:6]}@test.ru",
                password_hash=hash_password("pass"),
                role="owner",
            )
            db.add(user)
            await db.flush()
            venue = Venue(
                id=uuid.uuid4(),
                owner_id=user.id,
                name="WS Venue",
                slug=f"ws-{uuid.uuid4().hex[:6]}",
            )
            db.add(venue)
            await db.flush()
            table = Table(id=uuid.uuid4(), venue_id=venue.id, number=1, label="Стол 1")
            db.add(table)
            await db.commit()
            return str(venue.id), str(table.id)
    return _run(_create())


@pytest.fixture(scope="module")
def sync_client():
    async def _override_db():
        async with _SessionLocal() as session:
            yield session
    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_ws_table_connect_and_join(sync_client, ws_venue_table):
    venue_id, table_id = ws_venue_table
    guest_id = str(uuid.uuid4())
    with sync_client.websocket_connect(
        f"/ws/table/{table_id}?guest_id={guest_id}&venue_id={venue_id}"
    ) as ws:
        ws.send_json({
            "type": "guest_join",
            "payload": {"guest_id": guest_id, "guest_name": "Тест", "venue_id": venue_id},
        })
        msg = ws.receive_json()
        assert msg["type"] == "table_joined"
        assert "cart" in msg["payload"]
        assert "guests" in msg["payload"]


def test_ws_table_add_item(sync_client, ws_venue_table):
    venue_id, table_id = ws_venue_table
    guest_id = str(uuid.uuid4())
    dish_id = str(uuid.uuid4())
    with sync_client.websocket_connect(
        f"/ws/table/{table_id}?guest_id={guest_id}&venue_id={venue_id}"
    ) as ws:
        ws.send_json({
            "type": "guest_join",
            "payload": {"guest_id": guest_id, "guest_name": "Иван", "venue_id": venue_id},
        })
        ws.receive_json()  # table_joined
        ws.send_json({
            "type": "add_item",
            "payload": {
                "dish_id": dish_id,
                "dish_name": "Борщ",
                "unit_price": 350.0,
                "quantity": 1,
                "comment": "",
                "guest_id": guest_id,
                "guest_name": "Иван",
            },
        })
        msg = ws.receive_json()
        assert msg["type"] == "cart_updated"
        assert msg["payload"]["action"] == "add"
        assert len(msg["payload"]["cart"]) == 1


def test_ws_table_ping_pong(sync_client, ws_venue_table):
    venue_id, table_id = ws_venue_table
    guest_id = str(uuid.uuid4())
    with sync_client.websocket_connect(
        f"/ws/table/{table_id}?guest_id={guest_id}&venue_id={venue_id}"
    ) as ws:
        ws.send_json({
            "type": "guest_join",
            "payload": {"guest_id": guest_id, "guest_name": "P", "venue_id": venue_id},
        })
        ws.receive_json()  # table_joined
        ws.send_json({"type": "ping", "payload": {}})
        msg = ws.receive_json()
        assert msg["type"] == "pong"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && python3 -m pytest tests/test_ws_table.py -v
```

Expected: FAIL — WS route `/ws/table/{table_id}` not found.

- [ ] **Step 3: Create backend/app/ws/__init__.py** (empty file)

- [ ] **Step 4: Create backend/app/ws/table.py**

```python
import asyncio
import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.table import Table
from app.models.venue import Venue
from app.services.table_session import TableSessionService
from app.services.order_service import create_order
from app.schemas.order import OrderCreate, OrderItemCreate
from sqlalchemy import select


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

    # Resolve table + venue from DB
    table_result = await db.execute(
        select(Table).where(Table.id == table_id)
    )
    table = table_result.scalar_one_or_none()
    if not table:
        await websocket.close(code=4004, reason="Table not found")
        return

    venue_result = await db.execute(
        select(Venue).where(Venue.id == table.venue_id)
    )
    venue = venue_result.scalar_one_or_none()
    if not venue:
        await websocket.close(code=4004, reason="Venue not found")
        return

    pub_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    sub_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    svc = TableSessionService(pub_redis)

    table_channel = f"table:{table_id}"
    venue_id_str = str(table.venue_id)

    # Subscribe to table channel for broadcast
    pubsub = sub_redis.pubsub()
    await pubsub.subscribe(table_channel)

    session = await svc.get_or_create(venue_id_str, str(table_id))

    async def forward_pubsub():
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"])
        except Exception:
            pass

    forward_task = asyncio.create_task(forward_pubsub())

    async def publish(type_: str, payload: dict):
        await pub_redis.publish(table_channel, _msg(type_, payload))

    try:
        # Send initial state — wait for guest_join event first
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
                # Send table_joined only to this connection (not via pub/sub)
                await websocket.send_text(_msg("table_joined", {
                    "session_id": session["session_id"],
                    "table": {"id": str(table.id), "number": table.number, "label": table.label},
                    "guests": session["guests"],
                    "cart": session["cart"],
                    "total": session["total"],
                }))
                # Broadcast guest_connected to others
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
                await publish("cart_updated", {
                    "action": "add",
                    "cart_item": item,
                    "cart": result["cart"],
                    "total": result["total"],
                })
                continue

            if event_type == "remove_item":
                result = await svc.remove_cart_item(
                    venue_id_str, str(table_id),
                    payload["cart_item_id"],
                    payload["guest_id"],
                )
                await publish("cart_updated", {
                    "action": "remove",
                    "cart_item": {"cart_item_id": payload["cart_item_id"]},
                    "cart": result["cart"],
                    "total": result["total"],
                })
                continue

            if event_type == "update_qty":
                result = await svc.update_cart_qty(
                    venue_id_str, str(table_id),
                    payload["cart_item_id"],
                    int(payload["quantity"]),
                    payload["guest_id"],
                )
                await publish("cart_updated", {
                    "action": "update",
                    "cart_item": {"cart_item_id": payload["cart_item_id"], "quantity": payload["quantity"]},
                    "cart": result["cart"],
                    "total": result["total"],
                })
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
                # Notify kitchen
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
```

- [ ] **Step 5: Update backend/app/main.py to mount the table WS route**

```python
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uuid as uuid_mod

from app.api.auth import router as auth_router
from app.api.venues import router as venues_router
from app.api.tables import router as tables_router
from app.api.categories import router as categories_router
from app.api.dishes import router as dishes_router
from app.api.menu import router as menu_router
from app.api.parse import router as parse_router
from app.api.qr import router as qr_router
from app.api.orders import router as orders_router
from app.core.database import get_db

app = FastAPI(title="MenuScan API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(venues_router)
app.include_router(tables_router)
app.include_router(categories_router)
app.include_router(dishes_router)
app.include_router(menu_router)
app.include_router(parse_router)
app.include_router(qr_router)
app.include_router(orders_router)


@app.websocket("/ws/table/{table_id}")
async def websocket_table(
    websocket: WebSocket,
    table_id: uuid_mod.UUID,
    guest_id: str = "",
    venue_id: str = "",
):
    from app.ws.table import ws_table_handler
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await ws_table_handler(websocket, table_id, guest_id, venue_id, db)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run WebSocket tests**

```bash
cd backend && python3 -m pytest tests/test_ws_table.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 7: Run full test suite**

```bash
cd backend && python3 -m pytest tests/ -v --tb=short
```

Expected: All 36 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/ws/ backend/app/main.py backend/tests/test_ws_table.py
git commit -m "feat: table WebSocket handler with Redis Pub/Sub cart sync"
```

---

## Task 5: Kitchen WebSocket Handler

**Files:**
- Create: `backend/app/ws/kitchen.py`
- Modify: `backend/app/main.py`

Kitchen WebSocket auth: accepts the venue owner's JWT token as a query param `token`. On connection, verifies the token and checks the owner owns the given venue.

- [ ] **Step 1: Create backend/app/ws/kitchen.py**

```python
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


async def ws_kitchen_handler(
    websocket: WebSocket,
    venue_id: uuid.UUID,
    token: str,
    db: AsyncSession,
):
    await websocket.accept()

    # Verify token and ownership
    user_id_str = decode_access_token(token)
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
        # Fetch table
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
                    "dish_name": "",  # dish name not stored in order_item, use dish_id
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
```

- [ ] **Step 2: Add kitchen WS route to backend/app/main.py**

Add the kitchen WebSocket route after the table WS route (keep all other content the same):

```python
@app.websocket("/ws/kitchen/{venue_id}")
async def websocket_kitchen(
    websocket: WebSocket,
    venue_id: uuid_mod.UUID,
    token: str = "",
):
    from app.ws.kitchen import ws_kitchen_handler
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await ws_kitchen_handler(websocket, venue_id, token, db)
```

- [ ] **Step 3: Run full test suite**

```bash
cd backend && python3 -m pytest tests/ -v --tb=short
```

Expected: All 36 tests still PASS.

- [ ] **Step 4: Manual smoke test (optional — requires running services)**

```bash
# Start services
docker compose up -d

# Register + get token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"chef@test.ru","password":"Pass123","full_name":"Chef"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token: $TOKEN"
```

Expected: token printed without error.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ws/kitchen.py backend/app/main.py
git commit -m "feat: kitchen WebSocket handler with order status broadcast"
```

---

## Task 6: Guest App — Next.js 14 PWA Scaffold

**Files:**
- Create: `frontend/apps/guest/package.json`
- Create: `frontend/apps/guest/next.config.js`
- Create: `frontend/apps/guest/tsconfig.json`
- Create: `frontend/apps/guest/tailwind.config.js`
- Create: `frontend/apps/guest/postcss.config.js`
- Create: `frontend/apps/guest/public/manifest.json`
- Create: `frontend/apps/guest/app/layout.tsx`
- Create: `frontend/apps/guest/app/globals.css`

- [ ] **Step 1: Create frontend/apps/guest/package.json**

```json
{
  "name": "menuscan-guest",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.4",
    "react": "^18",
    "react-dom": "^18",
    "zustand": "^4.5.2"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "autoprefixer": "^10.0.1",
    "postcss": "^8",
    "tailwindcss": "^3.4.1",
    "typescript": "^5"
  }
}
```

- [ ] **Step 2: Create frontend/apps/guest/next.config.js**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
};

module.exports = nextConfig;
```

- [ ] **Step 3: Create frontend/apps/guest/tsconfig.json**

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: Create frontend/apps/guest/tailwind.config.js**

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: "#FF6B35",
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 5: Create frontend/apps/guest/postcss.config.js**

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 6: Create frontend/apps/guest/public/manifest.json**

```json
{
  "name": "MenuScan",
  "short_name": "MenuScan",
  "description": "Цифровое меню ресторана",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#FF6B35",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

- [ ] **Step 7: Create frontend/apps/guest/app/globals.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --brand: #FF6B35;
}

body {
  @apply bg-gray-50 text-gray-900;
}
```

- [ ] **Step 8: Create frontend/apps/guest/app/layout.tsx**

```tsx
import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MenuScan",
  description: "Цифровое меню ресторана",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#FF6B35",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 9: Install dependencies and verify build**

```bash
cd frontend/apps/guest
npm install
npm run build
```

Expected: Build succeeds (no pages yet, just the layout).

- [ ] **Step 10: Commit**

```bash
git add frontend/apps/guest/
git commit -m "feat: Guest App Next.js 14 PWA scaffold"
```

---

## Task 7: Guest App — Menu Page + Dish Cards

**Files:**
- Create: `frontend/apps/guest/lib/api.ts`
- Create: `frontend/apps/guest/app/[slug]/table/[tableNumber]/page.tsx`
- Create: `frontend/apps/guest/components/DishCard.tsx`
- Create: `frontend/apps/guest/components/CategoryTabs.tsx`

- [ ] **Step 1: Create frontend/apps/guest/lib/api.ts**

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Dish {
  id: string;
  name: string;
  description: string | null;
  price: number;
  weight: string | null;
  calories: string | null;
  image_url: string | null;
  tags: string[];
  allergens: string[];
  is_available: boolean;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  sort_order: number;
  dishes: Dish[];
}

export interface PublicMenu {
  venue: {
    id: string;
    name: string;
    logo_url: string | null;
    settings: Record<string, unknown>;
  };
  categories: Category[];
}

export interface TableInfo {
  id: string;
  number: number;
  label: string | null;
}

export async function fetchMenu(slug: string): Promise<PublicMenu> {
  const res = await fetch(`${API_BASE}/menu/${slug}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Menu not found");
  return res.json();
}

export async function fetchTableInfo(
  slug: string,
  tableNumber: number
): Promise<TableInfo> {
  const res = await fetch(`${API_BASE}/menu/${slug}/table/${tableNumber}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Table not found");
  return res.json();
}
```

- [ ] **Step 2: Create frontend/apps/guest/components/CategoryTabs.tsx**

```tsx
"use client";

import { Category } from "@/lib/api";

interface Props {
  categories: Category[];
  activeSlug: string;
  onSelect: (slug: string) => void;
}

export default function CategoryTabs({ categories, activeSlug, onSelect }: Props) {
  return (
    <div className="sticky top-0 z-10 bg-white border-b border-gray-200 overflow-x-auto">
      <div className="flex gap-1 px-4 py-2 min-w-max">
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => onSelect(cat.slug)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
              activeSlug === cat.slug
                ? "bg-orange-500 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {cat.name}
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create frontend/apps/guest/components/DishCard.tsx**

```tsx
"use client";

import { Dish } from "@/lib/api";

interface Props {
  dish: Dish;
  onAdd: (dish: Dish) => void;
}

export default function DishCard({ dish, onAdd }: Props) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex gap-3 p-4">
      {dish.image_url && (
        <img
          src={dish.image_url}
          alt={dish.name}
          className="w-20 h-20 object-cover rounded-lg flex-shrink-0"
        />
      )}
      <div className="flex-1 min-w-0">
        <h3 className="font-semibold text-gray-900 text-sm leading-tight">{dish.name}</h3>
        {dish.description && (
          <p className="text-gray-500 text-xs mt-0.5 line-clamp-2">{dish.description}</p>
        )}
        <div className="flex items-center gap-2 mt-1">
          {dish.weight && (
            <span className="text-xs text-gray-400">{dish.weight}</span>
          )}
          {dish.calories && (
            <span className="text-xs text-gray-400">{dish.calories}</span>
          )}
        </div>
        <div className="flex items-center justify-between mt-2">
          <span className="font-bold text-gray-900">
            {Number(dish.price).toLocaleString("ru-RU")} ₽
          </span>
          {dish.is_available ? (
            <button
              onClick={() => onAdd(dish)}
              className="bg-orange-500 hover:bg-orange-600 text-white text-sm font-semibold px-4 py-1.5 rounded-lg transition-colors"
            >
              + В корзину
            </button>
          ) : (
            <span className="text-xs text-gray-400">Недоступно</span>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create frontend/apps/guest/app/[slug]/table/[tableNumber]/page.tsx**

```tsx
import { notFound } from "next/navigation";
import { fetchMenu, fetchTableInfo } from "@/lib/api";
import MenuView from "./menu-view";

interface Props {
  params: { slug: string; tableNumber: string };
}

export default async function TablePage({ params }: Props) {
  const tableNumber = parseInt(params.tableNumber, 10);
  if (isNaN(tableNumber)) return notFound();

  let menu, tableInfo;
  try {
    [menu, tableInfo] = await Promise.all([
      fetchMenu(params.slug),
      fetchTableInfo(params.slug, tableNumber),
    ]);
  } catch {
    return notFound();
  }

  return (
    <MenuView
      menu={menu}
      tableInfo={tableInfo}
      venueSlug={params.slug}
    />
  );
}
```

- [ ] **Step 5: Create frontend/apps/guest/app/[slug]/table/[tableNumber]/menu-view.tsx**

```tsx
"use client";

import { useState, useMemo } from "react";
import type { PublicMenu, TableInfo, Dish } from "@/lib/api";
import CategoryTabs from "@/components/CategoryTabs";
import DishCard from "@/components/DishCard";

interface Props {
  menu: PublicMenu;
  tableInfo: TableInfo;
  venueSlug: string;
}

export default function MenuView({ menu, tableInfo, venueSlug }: Props) {
  const [activeSlug, setActiveSlug] = useState(
    menu.categories[0]?.slug ?? ""
  );
  const [search, setSearch] = useState("");

  const filteredCategories = useMemo(() => {
    if (!search.trim()) return menu.categories;
    const q = search.toLowerCase();
    return menu.categories
      .map((cat) => ({
        ...cat,
        dishes: cat.dishes.filter(
          (d) =>
            d.name.toLowerCase().includes(q) ||
            (d.description ?? "").toLowerCase().includes(q)
        ),
      }))
      .filter((cat) => cat.dishes.length > 0);
  }, [menu.categories, search]);

  const activeCategory =
    filteredCategories.find((c) => c.slug === activeSlug) ??
    filteredCategories[0];

  function handleAddDish(dish: Dish) {
    // Will be wired to cart store in Task 8
    alert(`Добавлено: ${dish.name}`);
  }

  return (
    <div className="max-w-lg mx-auto min-h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white px-4 pt-4 pb-2 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h1 className="text-lg font-bold text-gray-900">{menu.venue.name}</h1>
            <p className="text-sm text-gray-500">
              {tableInfo.label ?? `Стол ${tableInfo.number}`}
            </p>
          </div>
        </div>
        <input
          type="search"
          placeholder="Поиск по меню..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-gray-100 rounded-lg px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-500"
        />
      </div>

      {/* Category tabs */}
      {!search && (
        <CategoryTabs
          categories={menu.categories}
          activeSlug={activeSlug}
          onSelect={setActiveSlug}
        />
      )}

      {/* Dish list */}
      <div className="flex-1 px-4 py-4 space-y-3 pb-24">
        {(search ? filteredCategories : activeCategory ? [activeCategory] : []).map(
          (cat) => (
            <div key={cat.id}>
              {search && (
                <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  {cat.name}
                </h2>
              )}
              {cat.dishes.map((dish) => (
                <div key={dish.id} className="mb-3">
                  <DishCard dish={dish} onAdd={handleAddDish} />
                </div>
              ))}
            </div>
          )
        )}
        {filteredCategories.length === 0 && (
          <p className="text-center text-gray-400 mt-12">Ничего не найдено</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Build to verify no TypeScript errors**

```bash
cd frontend/apps/guest
npm run build
```

Expected: Build succeeds.

- [ ] **Step 7: Start dev server and verify the page loads**

```bash
cd frontend/apps/guest
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

In a browser, open `http://localhost:3000/{slug}/table/1` where `{slug}` is a venue you created via the API. Expected: menu page renders with categories, dishes, and search.

Stop the dev server with Ctrl+C.

- [ ] **Step 8: Commit**

```bash
git add frontend/apps/guest/lib/api.ts frontend/apps/guest/components/ frontend/apps/guest/app/
git commit -m "feat: guest app menu page with category tabs, dish cards, and search"
```

---

## Task 8: Guest App — WebSocket Cart

**Files:**
- Create: `frontend/apps/guest/lib/cartStore.ts`
- Create: `frontend/apps/guest/lib/useTableWebSocket.ts`
- Create: `frontend/apps/guest/components/CartDrawer.tsx`
- Create: `frontend/apps/guest/components/GuestNameModal.tsx`
- Modify: `frontend/apps/guest/app/[slug]/table/[tableNumber]/menu-view.tsx`

- [ ] **Step 1: Create frontend/apps/guest/lib/cartStore.ts**

```typescript
import { create } from "zustand";

export interface CartItem {
  cart_item_id: string;
  dish_id: string;
  dish_name: string;
  unit_price: number;
  quantity: number;
  comment: string;
  guest_id: string;
  guest_name: string;
}

export interface Guest {
  guest_id: string;
  guest_name: string;
}

interface CartStore {
  // Local identity
  guestId: string;
  guestName: string;
  setGuestName: (name: string) => void;

  // Server-synced state
  cart: CartItem[];
  total: number;
  guests: Guest[];
  sessionId: string | null;

  // WebSocket connection state
  wsStatus: "disconnected" | "connecting" | "connected";
  setWsStatus: (status: "disconnected" | "connecting" | "connected") => void;

  // Actions dispatched via WS (stored as pending, resolved on server echo)
  setCart: (cart: CartItem[], total: number) => void;
  setGuests: (guests: Guest[]) => void;
  setSessionId: (id: string) => void;

  // Order state
  lastOrder: { order_id: string; status: string; total_amount: number } | null;
  setLastOrder: (order: { order_id: string; status: string; total_amount: number }) => void;
  updateOrderStatus: (order_id: string, status: string) => void;
}

function getOrCreateGuestId(): string {
  if (typeof window === "undefined") return "guest-ssr";
  let id = localStorage.getItem("menuscan_guest_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("menuscan_guest_id", id);
  }
  return id;
}

export const useCartStore = create<CartStore>((set, get) => ({
  guestId: getOrCreateGuestId(),
  guestName: typeof window !== "undefined" ? localStorage.getItem("menuscan_guest_name") ?? "" : "",
  setGuestName: (name) => {
    if (typeof window !== "undefined") localStorage.setItem("menuscan_guest_name", name);
    set({ guestName: name });
  },

  cart: [],
  total: 0,
  guests: [],
  sessionId: null,
  wsStatus: "disconnected",

  setWsStatus: (wsStatus) => set({ wsStatus }),
  setCart: (cart, total) => set({ cart, total }),
  setGuests: (guests) => set({ guests }),
  setSessionId: (sessionId) => set({ sessionId }),

  lastOrder: null,
  setLastOrder: (order) => set({ lastOrder: order }),
  updateOrderStatus: (order_id, status) => {
    const o = get().lastOrder;
    if (o && o.order_id === order_id) set({ lastOrder: { ...o, status } });
  },
}));
```

- [ ] **Step 2: Create frontend/apps/guest/lib/useTableWebSocket.ts**

```typescript
"use client";

import { useEffect, useRef, useCallback } from "react";
import { useCartStore } from "./cartStore";

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  .replace(/^http/, "ws");

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000];

export function useTableWebSocket(tableId: string, venueId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const mountedRef = useRef(true);

  const { guestId, guestName, setWsStatus, setCart, setGuests, setSessionId, setLastOrder, updateOrderStatus } =
    useCartStore();

  const send = useCallback((type: string, payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    setWsStatus("connecting");

    const url = `${WS_BASE}/ws/table/${tableId}?guest_id=${guestId}&venue_id=${venueId}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      setWsStatus("connected");
      ws.send(
        JSON.stringify({
          type: "guest_join",
          payload: { guest_id: guestId, guest_name: guestName || "Гость", venue_id: venueId },
        })
      );
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      const { type, payload } = msg;

      if (type === "table_joined") {
        setSessionId(payload.session_id);
        setCart(payload.cart, payload.total);
        setGuests(payload.guests);
      }

      if (type === "cart_updated") {
        setCart(payload.cart, payload.total);
      }

      if (type === "guest_connected" || type === "guest_disconnected") {
        // Re-request state via next update; guests list comes in table_joined
      }

      if (type === "order_confirmed") {
        setLastOrder({
          order_id: payload.order_id,
          status: payload.status,
          total_amount: payload.total_amount,
        });
        setCart([], 0);
      }

      if (type === "order_status_changed") {
        updateOrderStatus(payload.order_id, payload.status);
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setWsStatus("disconnected");
      const delay = RECONNECT_DELAYS[Math.min(attemptRef.current, RECONNECT_DELAYS.length - 1)];
      attemptRef.current++;
      setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [tableId, venueId, guestId, guestName, setWsStatus, setCart, setGuests, setSessionId, setLastOrder, updateOrderStatus]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  return { send, wsRef };
}
```

- [ ] **Step 3: Create frontend/apps/guest/components/GuestNameModal.tsx**

```tsx
"use client";

import { useState } from "react";
import { useCartStore } from "@/lib/cartStore";

interface Props {
  onConfirm: (name: string) => void;
}

export default function GuestNameModal({ onConfirm }: Props) {
  const [name, setName] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim() || "Гость";
    onConfirm(trimmed);
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-end z-50">
      <div className="bg-white w-full max-w-lg mx-auto rounded-t-2xl p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-1">Как вас зовут?</h2>
        <p className="text-sm text-gray-500 mb-4">
          Другие гости за столом будут видеть ваше имя в корзине.
        </p>
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            autoFocus
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Имя (необязательно)"
            className="flex-1 bg-gray-100 rounded-lg px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-orange-500"
          />
          <button
            type="submit"
            className="bg-orange-500 hover:bg-orange-600 text-white font-semibold px-5 py-2.5 rounded-lg"
          >
            Войти
          </button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create frontend/apps/guest/components/CartDrawer.tsx**

```tsx
"use client";

import { useCartStore } from "@/lib/cartStore";

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmitOrder: () => void;
}

export default function CartDrawer({ open, onClose, onSubmitOrder }: Props) {
  const { cart, total, guestId } = useCartStore();

  if (!open) return null;

  const myItems = cart.filter((i) => i.guest_id === guestId);
  const othersItems = cart.filter((i) => i.guest_id !== guestId);

  return (
    <div className="fixed inset-0 z-40 flex items-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white w-full max-w-lg mx-auto rounded-t-2xl p-5 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Корзина стола</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
        </div>

        {cart.length === 0 && (
          <p className="text-gray-400 text-center py-6">Корзина пуста</p>
        )}

        {myItems.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Ваш заказ</p>
            {myItems.map((item) => (
              <div key={item.cart_item_id} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
                <div>
                  <p className="text-sm font-medium">{item.dish_name}</p>
                  {item.comment && <p className="text-xs text-gray-400">{item.comment}</p>}
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold">{(item.unit_price * item.quantity).toLocaleString("ru-RU")} ₽</p>
                  <p className="text-xs text-gray-400">{item.quantity} шт × {Number(item.unit_price).toLocaleString("ru-RU")} ₽</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {othersItems.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Другие гости</p>
            {othersItems.map((item) => (
              <div key={item.cart_item_id} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
                <div>
                  <p className="text-sm font-medium">{item.dish_name}</p>
                  <p className="text-xs text-gray-400">{item.guest_name}</p>
                </div>
                <p className="text-sm font-semibold">{(item.unit_price * item.quantity).toLocaleString("ru-RU")} ₽</p>
              </div>
            ))}
          </div>
        )}

        {cart.length > 0 && (
          <div className="sticky bottom-0 bg-white pt-3 border-t border-gray-100">
            <div className="flex justify-between items-center mb-3">
              <span className="font-semibold text-gray-700">Итого</span>
              <span className="font-bold text-lg">{total.toLocaleString("ru-RU")} ₽</span>
            </div>
            <button
              onClick={onSubmitOrder}
              className="w-full bg-orange-500 hover:bg-orange-600 text-white font-bold py-3 rounded-xl transition-colors"
            >
              Оформить заказ
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Update menu-view.tsx to wire up WebSocket + cart**

Replace `frontend/apps/guest/app/[slug]/table/[tableNumber]/menu-view.tsx` with:

```tsx
"use client";

import { useState, useMemo, useEffect } from "react";
import type { PublicMenu, TableInfo, Dish } from "@/lib/api";
import { useCartStore } from "@/lib/cartStore";
import { useTableWebSocket } from "@/lib/useTableWebSocket";
import CategoryTabs from "@/components/CategoryTabs";
import DishCard from "@/components/DishCard";
import CartDrawer from "@/components/CartDrawer";
import GuestNameModal from "@/components/GuestNameModal";

interface Props {
  menu: PublicMenu;
  tableInfo: TableInfo;
  venueSlug: string;
}

export default function MenuView({ menu, tableInfo, venueSlug }: Props) {
  const [activeSlug, setActiveSlug] = useState(menu.categories[0]?.slug ?? "");
  const [search, setSearch] = useState("");
  const [cartOpen, setCartOpen] = useState(false);
  const [nameAsked, setNameAsked] = useState(false);

  const {
    guestId,
    guestName,
    setGuestName,
    cart,
    total,
    wsStatus,
    lastOrder,
  } = useCartStore();

  const { send } = useTableWebSocket(tableInfo.id, menu.venue.id);

  // Ask for name once
  useEffect(() => {
    if (!guestName) setNameAsked(false);
    else setNameAsked(true);
  }, [guestName]);

  function handleSetName(name: string) {
    setGuestName(name);
    setNameAsked(true);
  }

  function handleAddDish(dish: Dish) {
    const cart_item_id = crypto.randomUUID();
    send("add_item", {
      cart_item_id,
      dish_id: dish.id,
      dish_name: dish.name,
      unit_price: Number(dish.price),
      quantity: 1,
      comment: "",
      guest_id: guestId,
      guest_name: guestName || "Гость",
    });
  }

  function handleSubmitOrder() {
    send("submit_order", { table_comment: "" });
    setCartOpen(false);
  }

  const filteredCategories = useMemo(() => {
    if (!search.trim()) return menu.categories;
    const q = search.toLowerCase();
    return menu.categories
      .map((cat) => ({
        ...cat,
        dishes: cat.dishes.filter(
          (d) =>
            d.name.toLowerCase().includes(q) ||
            (d.description ?? "").toLowerCase().includes(q)
        ),
      }))
      .filter((cat) => cat.dishes.length > 0);
  }, [menu.categories, search]);

  const activeCategory =
    filteredCategories.find((c) => c.slug === activeSlug) ?? filteredCategories[0];

  const statusLabel: Record<string, string> = {
    accepted: "✅ Принят",
    cooking: "👨‍🍳 Готовится",
    ready: "🎉 Готов!",
    served: "✔️ Подан",
  };

  return (
    <div className="max-w-lg mx-auto min-h-screen flex flex-col">
      {!nameAsked && <GuestNameModal onConfirm={handleSetName} />}

      {/* Header */}
      <div className="bg-white px-4 pt-4 pb-2 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h1 className="text-lg font-bold text-gray-900">{menu.venue.name}</h1>
            <p className="text-sm text-gray-500">
              {tableInfo.label ?? `Стол ${tableInfo.number}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${wsStatus === "connected" ? "bg-green-400" : "bg-gray-300"}`} />
            {cart.length > 0 && (
              <button
                onClick={() => setCartOpen(true)}
                className="bg-orange-500 text-white text-sm font-semibold px-3 py-1.5 rounded-lg"
              >
                🛒 {cart.length} · {total.toLocaleString("ru-RU")} ₽
              </button>
            )}
          </div>
        </div>

        {lastOrder && (
          <div className="bg-orange-50 border border-orange-200 rounded-lg px-3 py-2 mb-2 text-sm">
            Заказ #{lastOrder.order_id.slice(-6)}: {statusLabel[lastOrder.status] ?? lastOrder.status}
          </div>
        )}

        <input
          type="search"
          placeholder="Поиск по меню..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-gray-100 rounded-lg px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-500"
        />
      </div>

      {!search && (
        <CategoryTabs
          categories={menu.categories}
          activeSlug={activeSlug}
          onSelect={setActiveSlug}
        />
      )}

      <div className="flex-1 px-4 py-4 space-y-3 pb-24">
        {(search ? filteredCategories : activeCategory ? [activeCategory] : []).map((cat) => (
          <div key={cat.id}>
            {search && (
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
                {cat.name}
              </h2>
            )}
            {cat.dishes.map((dish) => (
              <div key={dish.id} className="mb-3">
                <DishCard dish={dish} onAdd={handleAddDish} />
              </div>
            ))}
          </div>
        ))}
        {filteredCategories.length === 0 && (
          <p className="text-center text-gray-400 mt-12">Ничего не найдено</p>
        )}
      </div>

      <CartDrawer
        open={cartOpen}
        onClose={() => setCartOpen(false)}
        onSubmitOrder={handleSubmitOrder}
      />
    </div>
  );
}
```

- [ ] **Step 6: Build to verify no TypeScript errors**

```bash
cd frontend/apps/guest
npm run build
```

Expected: Build succeeds.

- [ ] **Step 7: Manual end-to-end test**

```bash
# Terminal 1 — backend
docker compose up -d

# Terminal 2 — frontend
cd frontend/apps/guest
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

1. Register a user and create a venue with `table_count=3` via the API (or curl).
2. Open `http://localhost:3000/{slug}/table/1` in two separate browser tabs.
3. In Tab 1: enter a name, add a dish — verify Tab 2 shows the cart update in real time.
4. In Tab 1: click "Оформить заказ" — verify order confirmed banner appears.

- [ ] **Step 8: Commit**

```bash
git add frontend/apps/guest/lib/ frontend/apps/guest/components/ frontend/apps/guest/app/
git commit -m "feat: guest app WebSocket cart — real-time sync across guests at table"
```

---

## Task 9: Kitchen Display App

**Files:**
- Create: `frontend/apps/kitchen/package.json`
- Create: `frontend/apps/kitchen/next.config.js`
- Create: `frontend/apps/kitchen/tsconfig.json`
- Create: `frontend/apps/kitchen/tailwind.config.js`
- Create: `frontend/apps/kitchen/postcss.config.js`
- Create: `frontend/apps/kitchen/app/layout.tsx`
- Create: `frontend/apps/kitchen/app/globals.css`
- Create: `frontend/apps/kitchen/app/[venueId]/page.tsx`
- Create: `frontend/apps/kitchen/components/OrderCard.tsx`
- Create: `frontend/apps/kitchen/lib/useKitchenWebSocket.ts`

- [ ] **Step 1: Create frontend/apps/kitchen/package.json**

```json
{
  "name": "menuscan-kitchen",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3001",
    "build": "next build",
    "start": "next start -p 3001",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.4",
    "react": "^18",
    "react-dom": "^18",
    "zustand": "^4.5.2"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "autoprefixer": "^10.0.1",
    "postcss": "^8",
    "tailwindcss": "^3.4.1",
    "typescript": "^5"
  }
}
```

- [ ] **Step 2: Create frontend/apps/kitchen/next.config.js**

```js
/** @type {import('next').NextConfig} */
const nextConfig = { output: "standalone" };
module.exports = nextConfig;
```

- [ ] **Step 3: Create frontend/apps/kitchen/tsconfig.json**

Same content as guest app tsconfig.json (copy exactly):

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: Create frontend/apps/kitchen/tailwind.config.js**

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: { extend: {} },
  plugins: [],
};
```

- [ ] **Step 5: Create frontend/apps/kitchen/postcss.config.js**

```js
module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

- [ ] **Step 6: Create frontend/apps/kitchen/app/globals.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  @apply bg-gray-900 text-gray-100;
}
```

- [ ] **Step 7: Create frontend/apps/kitchen/app/layout.tsx**

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MenuScan Kitchen",
  description: "Кухонный экран",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 8: Create frontend/apps/kitchen/lib/useKitchenWebSocket.ts**

```typescript
"use client";

import { useEffect, useRef, useState, useCallback } from "react";

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  .replace(/^http/, "ws");

export interface KitchenOrderItem {
  dish_name: string;
  quantity: number;
  comment: string;
  guest_name: string;
}

export interface KitchenOrder {
  order_id: string;
  table: { number: number; label: string };
  status: "accepted" | "cooking" | "ready" | "served";
  total_amount: number;
  created_at: string;
  items: KitchenOrderItem[];
}

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000];

export function useKitchenWebSocket(venueId: string, token: string) {
  const [orders, setOrders] = useState<KitchenOrder[]>([]);
  const [status, setStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const mountedRef = useRef(true);

  const send = useCallback((type: string, payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    }
  }, []);

  const updateOrderStatus = useCallback((orderId: string, newStatus: KitchenOrder["status"]) => {
    send("update_order_status", { order_id: orderId, status: newStatus });
  }, [send]);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    setStatus("connecting");

    const url = `${WS_BASE}/ws/kitchen/${venueId}?token=${token}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      setStatus("connected");
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      const { type, payload } = msg;

      if (type === "kitchen_connected") {
        setOrders(payload.active_orders ?? []);
      }

      if (type === "new_order") {
        setOrders((prev) => [payload, ...prev]);
      }

      if (type === "order_status_updated") {
        setOrders((prev) =>
          prev.map((o) =>
            o.order_id === payload.order_id ? { ...o, status: payload.status } : o
          ).filter((o) => o.status !== "served")
        );
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setStatus("disconnected");
      const delay = RECONNECT_DELAYS[Math.min(attemptRef.current, RECONNECT_DELAYS.length - 1)];
      attemptRef.current++;
      setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, [venueId, token, send]);

  useEffect(() => {
    mountedRef.current = true;
    if (token) connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, [connect, token]);

  return { orders, status, updateOrderStatus };
}
```

- [ ] **Step 9: Create frontend/apps/kitchen/components/OrderCard.tsx**

```tsx
"use client";

import { KitchenOrder } from "@/lib/useKitchenWebSocket";

interface Props {
  order: KitchenOrder;
  onStatusChange: (orderId: string, status: KitchenOrder["status"]) => void;
}

const STATUS_LABEL: Record<string, string> = {
  accepted: "Принят",
  cooking: "Готовится",
  ready: "Готово!",
  served: "Подан",
};

const STATUS_COLOR: Record<string, string> = {
  accepted: "border-yellow-400 bg-yellow-950",
  cooking: "border-blue-400 bg-blue-950",
  ready: "border-green-400 bg-green-950",
  served: "border-gray-500 bg-gray-800",
};

const NEXT_STATUS: Record<string, KitchenOrder["status"]> = {
  accepted: "cooking",
  cooking: "ready",
  ready: "served",
};

const NEXT_LABEL: Record<string, string> = {
  accepted: "Начать готовку",
  cooking: "Готово",
  ready: "Подано",
};

export default function OrderCard({ order, onStatusChange }: Props) {
  const elapsed = Math.round((Date.now() - new Date(order.created_at).getTime()) / 60000);
  const nextStatus = NEXT_STATUS[order.status];

  return (
    <div className={`rounded-xl border-2 p-4 ${STATUS_COLOR[order.status] ?? "border-gray-600 bg-gray-800"}`}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <span className="text-lg font-bold">Стол {order.table.number}</span>
          {order.table.label && (
            <span className="text-sm text-gray-400 ml-2">{order.table.label}</span>
          )}
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold text-gray-300">{STATUS_LABEL[order.status]}</p>
          <p className="text-xs text-gray-500">{elapsed} мин назад</p>
        </div>
      </div>

      <div className="space-y-1.5 mb-4">
        {order.items.map((item, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className="font-bold text-orange-400 text-sm w-6 flex-shrink-0">{item.quantity}×</span>
            <div>
              <p className="text-sm font-medium">{item.dish_name || "Блюдо"}</p>
              {item.comment && <p className="text-xs text-gray-400 italic">{item.comment}</p>}
              {item.guest_name && <p className="text-xs text-gray-500">{item.guest_name}</p>}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-300">
          {Number(order.total_amount).toLocaleString("ru-RU")} ₽
        </span>
        {nextStatus && (
          <button
            onClick={() => onStatusChange(order.order_id, nextStatus)}
            className="bg-orange-500 hover:bg-orange-600 text-white text-sm font-bold px-4 py-2 rounded-lg transition-colors"
          >
            {NEXT_LABEL[order.status]}
          </button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 10: Create frontend/apps/kitchen/app/[venueId]/page.tsx**

```tsx
"use client";

import { useState } from "react";
import { useKitchenWebSocket } from "@/lib/useKitchenWebSocket";
import OrderCard from "@/components/OrderCard";

export default function KitchenPage({
  params,
  searchParams,
}: {
  params: { venueId: string };
  searchParams: { token?: string };
}) {
  const token = searchParams.token ?? "";
  const [filterStatus, setFilterStatus] = useState<string>("all");

  const { orders, status, updateOrderStatus } = useKitchenWebSocket(
    params.venueId,
    token
  );

  const filtered =
    filterStatus === "all"
      ? orders
      : orders.filter((o) => o.status === filterStatus);

  const counts = {
    accepted: orders.filter((o) => o.status === "accepted").length,
    cooking: orders.filter((o) => o.status === "cooking").length,
    ready: orders.filter((o) => o.status === "ready").length,
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
        <h1 className="text-lg font-bold">Кухонный экран</h1>
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              status === "connected" ? "bg-green-400" : "bg-red-400"
            }`}
          />
          <span className="text-sm text-gray-400">
            {status === "connected" ? "Подключено" : "Нет связи"}
          </span>
        </div>
      </div>

      {/* Status filter */}
      <div className="flex gap-2 px-6 py-3 bg-gray-800 border-b border-gray-700">
        {[
          { key: "all", label: "Все" },
          { key: "accepted", label: `Ожидают (${counts.accepted})` },
          { key: "cooking", label: `Готовятся (${counts.cooking})` },
          { key: "ready", label: `Готово (${counts.ready})` },
        ].map((f) => (
          <button
            key={f.key}
            onClick={() => setFilterStatus(f.key)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filterStatus === f.key
                ? "bg-orange-500 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Orders grid */}
      <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.length === 0 && (
          <div className="col-span-full text-center text-gray-500 py-16">
            {orders.length === 0 ? "Нет активных заказов" : "Нет заказов с таким статусом"}
          </div>
        )}
        {filtered.map((order) => (
          <OrderCard
            key={order.order_id}
            order={order}
            onStatusChange={updateOrderStatus}
          />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 11: Install dependencies and build**

```bash
cd frontend/apps/kitchen
npm install
npm run build
```

Expected: Build succeeds.

- [ ] **Step 12: Manual end-to-end test**

```bash
# Terminal 1 — backend (already running)

# Terminal 2 — guest app
cd frontend/apps/guest
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# Terminal 3 — kitchen app
cd frontend/apps/kitchen
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

1. Get a JWT token for the venue owner:
   ```bash
   TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"owner@test.ru","password":"Pass123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
   ```
2. Get the venue_id from `GET /venues` using the token.
3. Open kitchen at `http://localhost:3001/{venue_id}?token={TOKEN}`.
4. In another tab, open guest app at `http://localhost:3000/{slug}/table/1`.
5. Add dishes and submit order — order appears on kitchen screen.
6. Click "Начать готовку" on kitchen — status updates on guest screen.
7. Click "Готово" — guest sees "🎉 Готов!".

- [ ] **Step 13: Commit**

```bash
git add frontend/apps/kitchen/
git commit -m "feat: kitchen display app with real-time order management"
```

---

## Phase 2 Exit Criteria

- [ ] `pytest tests/ -v` → all 36+ backend tests PASS
- [ ] `npm run build` in `frontend/apps/guest` succeeds
- [ ] `npm run build` in `frontend/apps/kitchen` succeeds
- [ ] Guest opens QR URL → sees menu, can add dishes
- [ ] Two guests at same table → cart updates in real time on both screens
- [ ] Guest submits order → order appears on kitchen screen within 1 second
- [ ] Kitchen clicks status buttons → guest sees status update in real time
- [ ] WS reconnects after network drop (exponential backoff)
- [ ] `GET /menu/{slug}/table/{number}` returns table UUID

---

*When Phase 2 is complete: the full loop works — QR scan → menu → shared cart → order → kitchen display → status back to guest.*
