# MenuScan Phase 3 — Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the owner-facing dashboard SPA (Next.js 14) with menu management, tables/QR management, and analytics, plus three supporting backend endpoints.

**Architecture:** Mixed RSC + Client Islands. Server Components fetch initial data using httpOnly JWT cookie. Client Components handle interactive islands (MenuEditor, charts, OrdersTable). Server Actions handle all mutations. New backend endpoints: analytics aggregation, presigned S3 upload URL, category reorder, parser diff mode, orders pagination+CSV.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind CSS, Recharts, react-image-crop, @dnd-kit/core+sortable, @tanstack/react-table. Backend: FastAPI, asyncio.gather for parallel analytics queries, boto3 presigned URLs.

---

## File Map

```
backend/
├── app/
│   ├── models/parse_job.py         MODIFY — add diff_data JSONB column
│   ├── schemas/analytics.py        CREATE
│   ├── services/analytics_service.py  CREATE
│   ├── api/analytics.py            CREATE
│   ├── api/dishes.py               MODIFY — add upload-url endpoint
│   ├── api/categories.py           MODIFY — add reorder endpoint
│   ├── api/orders.py               MODIFY — add pagination + CSV
│   ├── api/parse.py                MODIFY — add apply-diff endpoint
│   ├── workers/parser.py           MODIFY — add diff_mode
│   └── main.py                     MODIFY — add analytics router
├── alembic/versions/
│   └── xxxx_parse_job_diff_data.py  CREATE
└── tests/
    ├── test_analytics.py           CREATE
    └── test_upload_reorder.py      CREATE

frontend/apps/dashboard/
├── package.json                    CREATE
├── next.config.js                  CREATE
├── tsconfig.json                   CREATE
├── tailwind.config.js              CREATE
├── postcss.config.js               CREATE
├── middleware.ts                   CREATE
├── app/
│   ├── layout.tsx                  CREATE
│   ├── globals.css                 CREATE
│   ├── (auth)/login/
│   │   ├── page.tsx                CREATE
│   │   └── login-form.tsx          CREATE
│   └── (dashboard)/
│       ├── layout.tsx              CREATE
│       ├── page.tsx                CREATE
│       └── venues/
│           ├── page.tsx            CREATE
│           └── [id]/
│               ├── menu/page.tsx   CREATE
│               ├── tables/page.tsx CREATE
│               └── analytics/page.tsx  CREATE
├── components/
│   ├── Sidebar.tsx                 CREATE
│   ├── menu/
│   │   ├── MenuEditor.tsx          CREATE
│   │   ├── MenuPageHeader.tsx      CREATE
│   │   ├── CategoryEditor.tsx      CREATE
│   │   ├── DishRow.tsx             CREATE
│   │   ├── ImageUpload.tsx         CREATE
│   │   └── DiffReview.tsx          CREATE
│   ├── tables/
│   │   ├── TableGrid.tsx           CREATE
│   │   └── QRPreview.tsx           CREATE
│   └── analytics/
│       ├── SummaryCards.tsx        CREATE
│       ├── PeriodFilter.tsx        CREATE
│       ├── RevenueChart.tsx        CREATE
│       ├── TopDishesChart.tsx      CREATE
│       └── OrdersTable.tsx         CREATE
└── lib/
    ├── api.ts                      CREATE
    ├── actions.ts                  CREATE
    └── auth.ts                     CREATE
```

---

## Task 1: Backend — Analytics Endpoint

**Files:**
- Create: `backend/app/schemas/analytics.py`
- Create: `backend/app/services/analytics_service.py`
- Create: `backend/app/api/analytics.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_analytics.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_analytics.py`:

```python
import pytest
import uuid as uuid_mod
from decimal import Decimal


async def _setup_with_order(client):
    email = f"an_{uuid_mod.uuid4().hex[:6]}@test.ru"
    r = await client.post("/auth/register", json={"email": email, "password": "Pass123", "full_name": "A"})
    token = r.json()["access_token"]
    vr = await client.post(
        "/venues",
        json={"name": f"V{uuid_mod.uuid4().hex[:4]}", "table_count": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    venue = vr.json()["venue"]
    tr = await client.get(f"/venues/{venue['id']}/tables", headers={"Authorization": f"Bearer {token}"})
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
    await client.post(
        "/orders",
        json={
            "venue_id": venue["id"],
            "table_id": table["id"],
            "session_id": "sess-analytics",
            "items": [{"dish_id": dish["id"], "guest_id": str(uuid_mod.uuid4()), "guest_name": "Тест", "quantity": 2, "unit_price": 350.00, "comment": ""}],
        },
    )
    return token, venue


@pytest.mark.asyncio
async def test_analytics_returns_summary(client):
    token, venue = await _setup_with_order(client)
    r = await client.get(
        f"/venues/{venue['id']}/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "daily" in data
    assert "top_dishes" in data
    assert data["summary"]["orders"] >= 1
    assert float(data["summary"]["revenue"]) >= 700.0


@pytest.mark.asyncio
async def test_analytics_with_date_filter(client):
    token, venue = await _setup_with_order(client)
    r = await client.get(
        f"/venues/{venue['id']}/analytics?from=2020-01-01&to=2020-01-02",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["orders"] == 0
    assert float(data["summary"]["revenue"]) == 0.0


@pytest.mark.asyncio
async def test_analytics_unauthorized(client):
    r = await client.get(f"/venues/{uuid_mod.uuid4()}/analytics")
    assert r.status_code == 403
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && python3 -m pytest tests/test_analytics.py -v
```

Expected: `ImportError` or 404 — analytics endpoint doesn't exist.

- [ ] **Step 3: Create backend/app/schemas/analytics.py**

```python
from pydantic import BaseModel
from decimal import Decimal


class DailyMetric(BaseModel):
    date: str
    revenue: Decimal
    orders: int


class TopDish(BaseModel):
    name: str
    count: int
    revenue: Decimal


class AnalyticsSummary(BaseModel):
    orders: int
    revenue: Decimal
    avg_check: Decimal
    top_dish: str | None


class AnalyticsOut(BaseModel):
    summary: AnalyticsSummary
    daily: list[DailyMetric]
    top_dishes: list[TopDish]
```

- [ ] **Step 4: Create backend/app/services/analytics_service.py**

```python
import asyncio
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, cast
from sqlalchemy.dialects.postgresql import DATE

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.dish import Dish
from app.schemas.analytics import AnalyticsOut, AnalyticsSummary, DailyMetric, TopDish


async def get_analytics(
    db: AsyncSession,
    venue_id: uuid.UUID,
    from_date: datetime,
    to_date: datetime,
) -> AnalyticsOut:
    base_filter = [
        Order.venue_id == venue_id,
        Order.created_at >= from_date,
        Order.created_at < to_date,
        Order.status != "cancelled",
    ]

    summary_stmt = select(
        func.count(Order.id).label("orders"),
        func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
        func.coalesce(func.avg(Order.total_amount), 0).label("avg_check"),
    ).where(*base_filter)

    daily_stmt = (
        select(
            cast(Order.created_at, DATE).label("date"),
            func.sum(Order.total_amount).label("revenue"),
            func.count(Order.id).label("orders"),
        )
        .where(*base_filter)
        .group_by(cast(Order.created_at, DATE))
        .order_by(cast(Order.created_at, DATE))
    )

    top_stmt = (
        select(
            Dish.name,
            func.count(OrderItem.id).label("count"),
            func.sum(OrderItem.unit_price * OrderItem.quantity).label("revenue"),
        )
        .join(Dish, Dish.id == OrderItem.dish_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(*base_filter)
        .group_by(Dish.id, Dish.name)
        .order_by(func.count(OrderItem.id).desc())
        .limit(10)
    )

    summary_result, daily_result, top_result = await asyncio.gather(
        db.execute(summary_stmt),
        db.execute(daily_stmt),
        db.execute(top_stmt),
    )

    summary_row = summary_result.one()
    top_rows = top_result.all()

    return AnalyticsOut(
        summary=AnalyticsSummary(
            orders=summary_row.orders,
            revenue=Decimal(str(summary_row.revenue)),
            avg_check=Decimal(str(summary_row.avg_check)),
            top_dish=top_rows[0].name if top_rows else None,
        ),
        daily=[
            DailyMetric(
                date=str(row.date),
                revenue=Decimal(str(row.revenue)),
                orders=row.orders,
            )
            for row in daily_result.all()
        ],
        top_dishes=[
            TopDish(
                name=row.name,
                count=row.count,
                revenue=Decimal(str(row.revenue)),
            )
            for row in top_rows
        ],
    )
```

- [ ] **Step 5: Create backend/app/api/analytics.py**

```python
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.analytics import AnalyticsOut
from app.services.analytics_service import get_analytics
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["analytics"])


@router.get("/{venue_id}/analytics", response_model=AnalyticsOut)
async def analytics(
    venue_id: uuid.UUID,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, user.id)
    now = datetime.now(timezone.utc)
    from_dt = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc) if from_date else now - timedelta(days=30)
    to_dt = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc) if to_date else now
    return await get_analytics(db, venue_id, from_dt, to_dt)
```

- [ ] **Step 6: Add analytics router to backend/app/main.py**

Add after `from app.api.orders import router as orders_router`:

```python
from app.api.analytics import router as analytics_router
```

Add after `app.include_router(orders_router)`:

```python
app.include_router(analytics_router)
```

- [ ] **Step 7: Run tests — expect PASS**

```bash
cd backend && python3 -m pytest tests/test_analytics.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 8: Run full suite**

```bash
cd backend && python3 -m pytest tests/ -v --tb=short
```

Expected: All existing tests still PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/analytics.py backend/app/services/analytics_service.py backend/app/api/analytics.py backend/app/main.py backend/tests/test_analytics.py
git commit -m "feat: analytics endpoint with revenue, daily breakdown, top dishes"
```

---

## Task 2: Backend — Upload URL + Category Reorder

**Files:**
- Modify: `backend/app/services/qr_service.py`
- Modify: `backend/app/api/dishes.py`
- Modify: `backend/app/api/categories.py`
- Create: `backend/tests/test_upload_reorder.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_upload_reorder.py`:

```python
import pytest
import uuid as uuid_mod


async def _setup(client):
    email = f"ur_{uuid_mod.uuid4().hex[:6]}@test.ru"
    r = await client.post("/auth/register", json={"email": email, "password": "Pass123", "full_name": "U"})
    token = r.json()["access_token"]
    vr = await client.post("/venues", json={"name": f"V{uuid_mod.uuid4().hex[:4]}", "table_count": 0}, headers={"Authorization": f"Bearer {token}"})
    venue = vr.json()["venue"]
    cr = await client.post(f"/venues/{venue['id']}/categories", json={"name": "A", "slug": "a"}, headers={"Authorization": f"Bearer {token}"})
    cat_a = cr.json()
    cr2 = await client.post(f"/venues/{venue['id']}/categories", json={"name": "B", "slug": "b", "sort_order": 1}, headers={"Authorization": f"Bearer {token}"})
    cat_b = cr2.json()
    dr = await client.post(f"/venues/{venue['id']}/dishes", json={"category_id": cat_a["id"], "name": "Суп", "price": 200}, headers={"Authorization": f"Bearer {token}"})
    dish = dr.json()
    return token, venue, cat_a, cat_b, dish


@pytest.mark.asyncio
async def test_category_reorder(client):
    token, venue, cat_a, cat_b, dish = await _setup(client)
    r = await client.patch(
        f"/venues/{venue['id']}/categories/reorder",
        json={"category_ids": [cat_b["id"], cat_a["id"]]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    cats = (await client.get(f"/venues/{venue['id']}/categories", headers={"Authorization": f"Bearer {token}"})).json()["categories"]
    assert cats[0]["id"] == cat_b["id"]
    assert cats[1]["id"] == cat_a["id"]


@pytest.mark.asyncio
async def test_upload_url_returns_presigned(client):
    token, venue, cat_a, cat_b, dish = await _setup(client)
    r = await client.post(
        f"/venues/{venue['id']}/dishes/{dish['id']}/upload-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "upload_url" in data
    assert "image_url" in data
    assert str(dish["id"]) in data["image_url"]


@pytest.mark.asyncio
async def test_upload_url_wrong_venue(client):
    token, venue, cat_a, cat_b, dish = await _setup(client)
    r = await client.post(
        f"/venues/{uuid_mod.uuid4()}/dishes/{dish['id']}/upload-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && python3 -m pytest tests/test_upload_reorder.py -v
```

Expected: All 3 FAIL (404s — endpoints don't exist).

- [ ] **Step 3: Add get_presigned_upload_url to backend/app/services/qr_service.py**

Add this function at the end of the file (after the existing functions):

```python
def get_presigned_upload_url(key: str) -> tuple[str, str]:
    s3 = _get_s3_client()
    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key, "ContentType": "image/jpeg"},
        ExpiresIn=300,
    )
    image_url = f"{settings.s3_public_url}/{settings.s3_bucket_name}/{key}"
    return upload_url, image_url
```

- [ ] **Step 4: Add upload-url endpoint to backend/app/api/dishes.py**

Add at the end of the file (after the delete endpoint):

```python
@router.post("/{venue_id}/dishes/{dish_id}/upload-url")
async def get_upload_url(
    venue_id: uuid.UUID,
    dish_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Dish).where(Dish.id == dish_id, Dish.venue_id == venue_id))
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    from app.services.qr_service import get_presigned_upload_url
    key = f"dishes/{venue_id}/{dish_id}.jpg"
    upload_url, image_url = get_presigned_upload_url(key)
    return {"upload_url": upload_url, "image_url": image_url}
```

- [ ] **Step 5: Add reorder endpoint to backend/app/api/categories.py**

Add at the top of the file, after existing imports, add `from pydantic import BaseModel`.

Then add at the end of the file:

```python
class CategoryReorder(BaseModel):
    category_ids: list[uuid.UUID]


@router.patch("/{venue_id}/categories/reorder")
async def reorder_categories(
    venue_id: uuid.UUID,
    data: CategoryReorder,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, user.id)
    for i, cat_id in enumerate(data.category_ids):
        result = await db.execute(
            select(Category).where(Category.id == cat_id, Category.venue_id == venue_id)
        )
        cat = result.scalar_one_or_none()
        if cat:
            cat.sort_order = i
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
cd backend && python3 -m pytest tests/test_upload_reorder.py -v
```

Expected: All 3 PASS.

- [ ] **Step 7: Run full suite**

```bash
cd backend && python3 -m pytest tests/ -v --tb=short
```

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/qr_service.py backend/app/api/dishes.py backend/app/api/categories.py backend/tests/test_upload_reorder.py
git commit -m "feat: presigned S3 upload URL for dish photos + category reorder endpoint"
```

---

## Task 3: Backend — Parser Diff Mode + Orders Pagination + CSV

**Files:**
- Modify: `backend/app/models/parse_job.py`
- Create: `backend/alembic/versions/` (migration)
- Modify: `backend/app/workers/parser.py`
- Modify: `backend/app/api/parse.py`
- Modify: `backend/app/api/orders.py`

- [ ] **Step 1: Add diff_data column to ParseJob model**

Replace the contents of `backend/app/models/parse_job.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from typing import Any
from app.models.base import Base


class ParseJob(Base):
    __tablename__ = "parse_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    dishes_found: Mapped[int] = mapped_column(Integer, default=0)
    diff_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    diff_data: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 2: Generate and apply migration**

```bash
cd backend
alembic revision --autogenerate -m "add_parse_job_diff_fields"
alembic upgrade head
```

Verify:
```bash
docker compose exec db psql -U menuscan -c "\d parse_jobs"
```

Expected: `diff_mode` and `diff_data` columns listed.

- [ ] **Step 3: Modify backend/app/workers/parser.py — add diff_mode support**

Replace `run_parse_job` function (keep all helper functions above it unchanged). Replace from `async def run_parse_job` to end of file:

```python
def _compute_diff(existing_dishes: list, parsed_dishes: list) -> list[dict]:
    existing_by_name = {d.name.lower(): d for d in existing_dishes}
    parsed_names = {d["name"].lower() for d in parsed_dishes}
    diff = []

    for parsed in parsed_dishes:
        name_key = parsed["name"].lower()
        if name_key in existing_by_name:
            existing = existing_by_name[name_key]
            changes = {}
            if parsed.get("price") is not None and abs(float(existing.price) - float(parsed["price"])) > 0.01:
                changes["old_price"] = float(existing.price)
                changes["new_price"] = float(parsed["price"])
            if parsed.get("weight") and parsed["weight"] != existing.weight:
                changes["old_weight"] = existing.weight
                changes["new_weight"] = parsed["weight"]
            if changes:
                diff.append({
                    "dish_id": str(existing.id),
                    "action": "update",
                    "name": existing.name,
                    **changes,
                })
        else:
            diff.append({
                "dish_id": None,
                "action": "add",
                "name": parsed["name"],
                "new_price": float(parsed["price"]),
                "new_weight": parsed.get("weight"),
                "description": parsed.get("description"),
            })

    for name_key, existing in existing_by_name.items():
        if name_key not in parsed_names:
            diff.append({
                "dish_id": str(existing.id),
                "action": "remove",
                "name": existing.name,
                "old_price": float(existing.price),
            })

    return diff


async def run_parse_job(db: AsyncSession, job_id: uuid.UUID) -> None:
    from app.models.parse_job import ParseJob
    from app.models.venue import Venue
    from app.models.category import Category
    from app.models.dish import Dish

    result = await db.execute(select(ParseJob).where(ParseJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    await db.commit()

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
            resp = await http.get(job.source_url)
            resp.raise_for_status()

        selectors = {
            "item": ".menu-item, .dish, .product, [class*='menu-item'], [class*='dish']",
            "name": ".name, .title, h3, h4, [class*='name'], [class*='title']",
            "price": ".price, [class*='price'], [class*='cost']",
            "weight": ".weight, .volume, [class*='weight'], [class*='gram']",
            "description": ".description, .desc, [class*='desc']",
        }
        dishes_data = extract_dishes_from_html(resp.text, selectors)

        venue_result = await db.execute(select(Venue).where(Venue.id == job.venue_id))
        venue = venue_result.scalar_one()

        if job.diff_mode:
            existing_result = await db.execute(select(Dish).where(Dish.venue_id == venue.id))
            existing_dishes = existing_result.scalars().all()
            diff = _compute_diff(existing_dishes, dishes_data)
            job.diff_data = diff
            job.status = "done"
            job.dishes_found = len(dishes_data)
            job.finished_at = datetime.now(timezone.utc)
            venue.parse_status = "done"
            await db.commit()
            return

        cat_result = await db.execute(
            select(Category).where(Category.venue_id == venue.id, Category.slug == "uncategorized")
        )
        default_cat = cat_result.scalar_one_or_none()
        if not default_cat:
            default_cat = Category(
                id=uuid.uuid4(), venue_id=venue.id, name="Меню", slug="uncategorized", sort_order=0
            )
            db.add(default_cat)
            await db.flush()

        for i, d in enumerate(dishes_data):
            db.add(Dish(
                id=uuid.uuid4(),
                venue_id=venue.id,
                category_id=default_cat.id,
                name=d["name"],
                price=d["price"],
                weight=d.get("weight"),
                description=d.get("description"),
                sort_order=i,
            ))

        job.status = "done"
        job.dishes_found = len(dishes_data)
        job.finished_at = datetime.now(timezone.utc)
        venue.parse_status = "done" if dishes_data else "failed"
        await db.commit()

    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        venue_result = await db.execute(select(Venue).where(Venue.id == job.venue_id))
        venue = venue_result.scalar_one()
        venue.parse_status = "failed"
        await db.commit()
```

- [ ] **Step 4: Update parse.py — update parse-status + add reparse-diff + apply-diff endpoints**

Replace the contents of `backend/app/api/parse.py`:

```python
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.parse_job import ParseJob
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["parsing"])


@router.get("/{venue_id}/parse-status")
async def parse_status(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(
        select(ParseJob).where(ParseJob.venue_id == venue_id).order_by(ParseJob.id.desc()).limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="No parse job found")
    return {
        "job_id": job.id,
        "status": job.status,
        "dishes_found": job.dishes_found,
        "diff_data": job.diff_data,
        "error_message": job.error_message,
        "finished_at": job.finished_at,
    }


@router.post("/{venue_id}/reparse", status_code=202)
async def reparse(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.venue import Venue
    venue = await get_venue_or_404(db, venue_id, user.id)
    if not venue.website_url:
        raise HTTPException(status_code=400, detail="No website URL set")

    job = ParseJob(id=uuid.uuid4(), venue_id=venue_id, source_url=venue.website_url, status="queued", diff_mode=False)
    db.add(job)
    venue.parse_status = "parsing"
    await db.commit()
    await db.refresh(job)

    from app.workers.parser import run_parse_job
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as bg_db:
            await run_parse_job(bg_db, job.id)

    asyncio.create_task(_run())
    return {"parse_job_id": job.id, "status": "queued"}


@router.post("/{venue_id}/reparse-diff", status_code=202)
async def reparse_diff(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.venue import Venue
    venue = await get_venue_or_404(db, venue_id, user.id)
    if not venue.website_url:
        raise HTTPException(status_code=400, detail="No website URL set")

    job = ParseJob(id=uuid.uuid4(), venue_id=venue_id, source_url=venue.website_url, status="queued", diff_mode=True)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    from app.workers.parser import run_parse_job
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as bg_db:
            await run_parse_job(bg_db, job.id)

    asyncio.create_task(_run())
    return {"parse_job_id": job.id, "status": "queued"}


class ApplyDiffRequest(BaseModel):
    changes: list[dict]


@router.post("/{venue_id}/parse/apply-diff")
async def apply_diff(
    venue_id: uuid.UUID,
    data: ApplyDiffRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.models.dish import Dish
    from app.models.category import Category

    await get_venue_or_404(db, venue_id, user.id)

    cat_result = await db.execute(
        select(Category).where(Category.venue_id == venue_id, Category.slug == "uncategorized")
    )
    default_cat = cat_result.scalar_one_or_none()

    for change in data.changes:
        action = change.get("action")
        dish_id = change.get("dish_id")

        if action == "update" and dish_id:
            result = await db.execute(select(Dish).where(Dish.id == uuid.UUID(dish_id), Dish.venue_id == venue_id))
            dish = result.scalar_one_or_none()
            if dish:
                if "new_price" in change:
                    dish.price = change["new_price"]
                if "new_weight" in change:
                    dish.weight = change["new_weight"]

        elif action == "add":
            if not default_cat:
                default_cat = Category(id=uuid.uuid4(), venue_id=venue_id, name="Меню", slug="uncategorized", sort_order=0)
                db.add(default_cat)
                await db.flush()
            db.add(Dish(
                id=uuid.uuid4(),
                venue_id=venue_id,
                category_id=default_cat.id,
                name=change["name"],
                price=change.get("new_price", 0),
                weight=change.get("new_weight"),
                description=change.get("description"),
            ))

        elif action == "remove" and dish_id:
            result = await db.execute(select(Dish).where(Dish.id == uuid.UUID(dish_id), Dish.venue_id == venue_id))
            dish = result.scalar_one_or_none()
            if dish:
                dish.is_available = False

    await db.commit()
    return {"ok": True}
```

- [ ] **Step 5: Add pagination + CSV to backend/app/api/orders.py**

Replace the `list_orders` function only (keep `post_order` and `patch_order_status` unchanged):

```python
import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func

# ... keep all existing imports ...

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
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    offset = (page - 1) * limit
    result = await db.execute(stmt.offset(offset).limit(limit))
    orders = result.scalars().all()

    out = []
    for order in orders:
        items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        order.__dict__["items"] = items_result.scalars().all()
        out.append(OrderOut.model_validate(order))
    return {"orders": out, "page": page, "limit": limit, "total": total}
```

Full updated `backend/app/api/orders.py`:

```python
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
```

- [ ] **Step 6: Run full test suite**

```bash
cd backend && python3 -m pytest tests/ -v --tb=short
```

Expected: All existing tests PASS (the orders test checks `r.json()["orders"]` which still exists).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/parse_job.py backend/alembic/ backend/app/workers/parser.py backend/app/api/parse.py backend/app/api/orders.py
git commit -m "feat: parser diff mode, apply-diff endpoint, orders pagination + CSV export"
```

---

## Task 4: Dashboard App Scaffold

**Files:**
- Create: `frontend/apps/dashboard/package.json`
- Create: `frontend/apps/dashboard/next.config.js`
- Create: `frontend/apps/dashboard/tsconfig.json`
- Create: `frontend/apps/dashboard/tailwind.config.js`
- Create: `frontend/apps/dashboard/postcss.config.js`
- Create: `frontend/apps/dashboard/app/layout.tsx`
- Create: `frontend/apps/dashboard/app/globals.css`

- [ ] **Step 1: Create frontend/apps/dashboard/package.json**

```json
{
  "name": "menuscan-dashboard",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3002",
    "build": "next build",
    "start": "next start -p 3002",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.4",
    "react": "^18",
    "react-dom": "^18",
    "recharts": "^2.12.3",
    "react-image-crop": "^11.0.5",
    "@dnd-kit/core": "^6.1.0",
    "@dnd-kit/sortable": "^8.0.0",
    "@dnd-kit/utilities": "^3.2.2",
    "@tanstack/react-table": "^8.17.3"
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

- [ ] **Step 2: Create frontend/apps/dashboard/next.config.js**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  experimental: {
    serverActions: { allowedOrigins: ["localhost:3002"] },
  },
};

module.exports = nextConfig;
```

- [ ] **Step 3: Create frontend/apps/dashboard/tsconfig.json**

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

- [ ] **Step 4: Create frontend/apps/dashboard/tailwind.config.js**

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: { brand: "#FF6B35" },
    },
  },
  plugins: [],
};
```

- [ ] **Step 5: Create frontend/apps/dashboard/postcss.config.js**

```js
module.exports = {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

- [ ] **Step 6: Create frontend/apps/dashboard/app/globals.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 7: Create frontend/apps/dashboard/app/layout.tsx**

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MenuScan Dashboard",
  description: "Управление цифровым меню",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 8: Install dependencies**

```bash
cd frontend/apps/dashboard && npm install
```

Expected: `node_modules` created, no errors.

- [ ] **Step 9: Verify build compiles**

```bash
cd frontend/apps/dashboard && npm run build
```

Expected: Build succeeds (no pages yet — Next.js emits an empty build).

- [ ] **Step 10: Commit**

```bash
git add frontend/apps/dashboard/
git commit -m "feat: Dashboard Next.js 14 app scaffold"
```

---

## Task 5: Dashboard — Auth (Login Page + Middleware)

**Files:**
- Create: `frontend/apps/dashboard/middleware.ts`
- Create: `frontend/apps/dashboard/lib/auth.ts`
- Create: `frontend/apps/dashboard/lib/actions.ts`
- Create: `frontend/apps/dashboard/app/(auth)/login/page.tsx`
- Create: `frontend/apps/dashboard/app/(auth)/login/login-form.tsx`

- [ ] **Step 1: Create frontend/apps/dashboard/middleware.ts**

```typescript
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("token")?.value;
  const path = request.nextUrl.pathname;
  const isLoginPage = path === "/login";

  if (!token && !isLoginPage) {
    const url = new URL("/login", request.url);
    url.searchParams.set("redirect", path);
    return NextResponse.redirect(url);
  }

  if (token && isLoginPage) {
    return NextResponse.redirect(new URL("/venues", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

- [ ] **Step 2: Create frontend/apps/dashboard/lib/auth.ts**

```typescript
import { cookies } from "next/headers";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken(): string | undefined {
  return cookies().get("token")?.value;
}

export async function getServerSession(): Promise<{ email: string; id: string } | null> {
  const token = getToken();
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
```

- [ ] **Step 3: Create frontend/apps/dashboard/lib/actions.ts**

```typescript
"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken() {
  return cookies().get("token")?.value ?? "";
}

export async function loginAction(
  _prevState: { error: string | null },
  formData: FormData
): Promise<{ error: string | null }> {
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;

  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) return { error: "Неверный email или пароль" };

  const { access_token } = await res.json();
  cookies().set("token", access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24,
  });
  redirect("/venues");
}

export async function logoutAction() {
  cookies().delete("token");
  redirect("/login");
}

export async function updateDishPrice(venueId: string, dishId: string, price: number): Promise<void> {
  await fetch(`${API_BASE}/venues/${venueId}/dishes/${dishId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ price }),
  });
  revalidatePath(`/venues/${venueId}/menu`);
}

export async function toggleDishAvailability(venueId: string, dishId: string, available: boolean): Promise<void> {
  await fetch(`${API_BASE}/venues/${venueId}/dishes/${dishId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ is_available: available }),
  });
  revalidatePath(`/venues/${venueId}/menu`);
}

export async function getUploadUrl(venueId: string, dishId: string): Promise<{ upload_url: string; image_url: string }> {
  const res = await fetch(`${API_BASE}/venues/${venueId}/dishes/${dishId}/upload-url`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return res.json();
}

export async function confirmDishImage(venueId: string, dishId: string, imageUrl: string): Promise<void> {
  await fetch(`${API_BASE}/venues/${venueId}/dishes/${dishId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ image_url: imageUrl }),
  });
  revalidatePath(`/venues/${venueId}/menu`);
}

export async function reorderCategories(venueId: string, categoryIds: string[]): Promise<void> {
  await fetch(`${API_BASE}/venues/${venueId}/categories/reorder`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ category_ids: categoryIds }),
  });
  revalidatePath(`/venues/${venueId}/menu`);
}

export async function applyParseDiff(venueId: string, changes: object[]): Promise<void> {
  await fetch(`${API_BASE}/venues/${venueId}/parse/apply-diff`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ changes }),
  });
  revalidatePath(`/venues/${venueId}/menu`);
}
```

- [ ] **Step 4: Create frontend/apps/dashboard/app/(auth)/login/page.tsx**

```tsx
import LoginForm from "./login-form";

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-orange-500">MenuScan</h1>
          <p className="text-gray-500 text-sm mt-1">Войдите в личный кабинет</p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create frontend/apps/dashboard/app/(auth)/login/login-form.tsx**

```tsx
"use client";

import { useFormState, useFormStatus } from "react-dom";
import { loginAction } from "@/lib/actions";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg transition-colors"
    >
      {pending ? "Входим..." : "Войти"}
    </button>
  );
}

export default function LoginForm() {
  const [state, formAction] = useFormState(loginAction, { error: null });
  return (
    <form action={formAction} className="space-y-4">
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
        <input id="email" name="email" type="email" required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-500" />
      </div>
      <div>
        <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
        <input id="password" name="password" type="password" required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-500" />
      </div>
      {state?.error && <p className="text-red-500 text-sm">{state.error}</p>}
      <SubmitButton />
    </form>
  );
}
```

- [ ] **Step 6: Build to verify no TS errors**

```bash
cd frontend/apps/dashboard && npm run build
```

Expected: Build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/apps/dashboard/middleware.ts frontend/apps/dashboard/lib/ frontend/apps/dashboard/app/\(auth\)/
git commit -m "feat: dashboard auth — login page, middleware, httpOnly cookie JWT"
```

---

## Task 6: Dashboard — Layout + Venue List

**Files:**
- Create: `frontend/apps/dashboard/lib/api.ts`
- Create: `frontend/apps/dashboard/components/Sidebar.tsx`
- Create: `frontend/apps/dashboard/app/(dashboard)/layout.tsx`
- Create: `frontend/apps/dashboard/app/(dashboard)/page.tsx`
- Create: `frontend/apps/dashboard/app/(dashboard)/venues/page.tsx`

- [ ] **Step 1: Create frontend/apps/dashboard/lib/api.ts**

```typescript
import { cookies } from "next/headers";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function authHeaders() {
  const token = cookies().get("token")?.value;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface Venue {
  id: string;
  name: string;
  slug: string;
  address: string | null;
  cuisine_type: string | null;
  table_count: number;
  parse_status: string;
  is_active: boolean;
  created_at: string;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  sort_order: number;
  is_visible: boolean;
}

export interface Dish {
  id: string;
  venue_id: string;
  category_id: string | null;
  name: string;
  description: string | null;
  price: string;
  weight: string | null;
  calories: string | null;
  image_url: string | null;
  tags: string[];
  allergens: string[];
  is_available: boolean;
  sort_order: number;
}

export interface Table {
  id: string;
  number: number;
  label: string | null;
  qr_code_url: string | null;
  is_active: boolean;
}

export interface Order {
  id: string;
  table_id: string;
  status: string;
  total_amount: string;
  created_at: string;
  session_id: string;
  items: Array<{
    id: string;
    dish_id: string;
    quantity: number;
    unit_price: string;
    guest_name: string | null;
  }>;
}

export interface AnalyticsData {
  summary: { orders: number; revenue: string; avg_check: string; top_dish: string | null };
  daily: Array<{ date: string; revenue: string; orders: number }>;
  top_dishes: Array<{ name: string; count: number; revenue: string }>;
}

export async function fetchVenues(): Promise<{ venues: Venue[] }> {
  const res = await fetch(`${API_BASE}/venues`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch venues");
  return res.json();
}

export async function fetchVenue(id: string): Promise<Venue> {
  const res = await fetch(`${API_BASE}/venues/${id}`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch venue");
  return res.json();
}

export async function fetchCategories(venueId: string): Promise<{ categories: Category[] }> {
  const res = await fetch(`${API_BASE}/venues/${venueId}/categories`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch categories");
  return res.json();
}

export async function fetchDishes(venueId: string): Promise<{ dishes: Dish[] }> {
  const res = await fetch(`${API_BASE}/venues/${venueId}/dishes`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch dishes");
  return res.json();
}

export async function fetchTables(venueId: string): Promise<{ tables: Table[] }> {
  const res = await fetch(`${API_BASE}/venues/${venueId}/tables`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch tables");
  return res.json();
}

export async function fetchAnalytics(venueId: string, from?: string, to?: string): Promise<AnalyticsData> {
  const sp = new URLSearchParams();
  if (from) sp.set("from", from);
  if (to) sp.set("to", to);
  const res = await fetch(`${API_BASE}/venues/${venueId}/analytics?${sp}`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch analytics");
  return res.json();
}
```

- [ ] **Step 2: Create frontend/apps/dashboard/components/Sidebar.tsx**

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { logoutAction } from "@/lib/actions";

export default function Sidebar({ userEmail }: { userEmail: string }) {
  const pathname = usePathname();
  return (
    <aside className="w-60 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
      <div className="p-6 border-b border-gray-100">
        <h1 className="text-xl font-bold text-orange-500">MenuScan</h1>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        <Link
          href="/venues"
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
            pathname.startsWith("/venues") ? "bg-orange-50 text-orange-600" : "text-gray-600 hover:bg-gray-50"
          }`}
        >
          Заведения
        </Link>
      </nav>
      <div className="p-4 border-t border-gray-100">
        <p className="text-xs text-gray-400 truncate mb-2">{userEmail}</p>
        <form action={logoutAction}>
          <button type="submit" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">
            Выйти
          </button>
        </form>
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Create frontend/apps/dashboard/app/(dashboard)/layout.tsx**

```tsx
import { redirect } from "next/navigation";
import { getServerSession } from "@/lib/auth";
import Sidebar from "@/components/Sidebar";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await getServerSession();
  if (!session) redirect("/login");
  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <Sidebar userEmail={session.email} />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
```

- [ ] **Step 4: Create frontend/apps/dashboard/app/(dashboard)/page.tsx**

```tsx
import { redirect } from "next/navigation";
export default function Home() {
  redirect("/venues");
}
```

- [ ] **Step 5: Create frontend/apps/dashboard/app/(dashboard)/venues/page.tsx**

```tsx
import Link from "next/link";
import { fetchVenues } from "@/lib/api";

export default async function VenuesPage() {
  const { venues } = await fetchVenues();
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-8">Мои заведения</h1>
      {venues.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg font-medium">Нет заведений</p>
          <p className="text-sm mt-1">Создайте заведение через API</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {venues.map((venue) => (
            <div key={venue.id} className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-bold text-gray-900">{venue.name}</h2>
                  {venue.address && <p className="text-gray-500 text-sm mt-0.5">{venue.address}</p>}
                </div>
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${venue.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                  {venue.is_active ? "Активно" : "Неактивно"}
                </span>
              </div>
              <p className="text-sm text-gray-500 mt-2">{venue.table_count} столов · {venue.slug}</p>
              <div className="flex gap-2 mt-4">
                <Link href={`/venues/${venue.id}/menu`} className="flex-1 text-center text-sm font-medium bg-orange-500 text-white py-2 rounded-lg hover:bg-orange-600 transition-colors">
                  Меню
                </Link>
                <Link href={`/venues/${venue.id}/tables`} className="flex-1 text-center text-sm font-medium border border-gray-200 text-gray-700 py-2 rounded-lg hover:bg-gray-50 transition-colors">
                  Столы
                </Link>
                <Link href={`/venues/${venue.id}/analytics`} className="flex-1 text-center text-sm font-medium border border-gray-200 text-gray-700 py-2 rounded-lg hover:bg-gray-50 transition-colors">
                  Аналитика
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Build to verify**

```bash
cd frontend/apps/dashboard && npm run build
```

Expected: Build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/apps/dashboard/lib/api.ts frontend/apps/dashboard/components/Sidebar.tsx frontend/apps/dashboard/app/\(dashboard\)/
git commit -m "feat: dashboard layout, sidebar, venue list page"
```

---

## Task 7: Dashboard — Menu Editor

**Files:**
- Create: `frontend/apps/dashboard/app/(dashboard)/venues/[id]/menu/page.tsx`
- Create: `frontend/apps/dashboard/components/menu/MenuPageHeader.tsx`
- Create: `frontend/apps/dashboard/components/menu/MenuEditor.tsx`
- Create: `frontend/apps/dashboard/components/menu/CategoryEditor.tsx`
- Create: `frontend/apps/dashboard/components/menu/DishRow.tsx`

- [ ] **Step 1: Create frontend/apps/dashboard/app/(dashboard)/venues/[id]/menu/page.tsx**

```tsx
import { fetchCategories, fetchDishes, fetchVenue } from "@/lib/api";
import MenuEditor from "@/components/menu/MenuEditor";
import MenuPageHeader from "@/components/menu/MenuPageHeader";

interface Props {
  params: { id: string };
}

export default async function MenuPage({ params }: Props) {
  const [venue, { categories }, { dishes }] = await Promise.all([
    fetchVenue(params.id),
    fetchCategories(params.id),
    fetchDishes(params.id),
  ]);
  return (
    <div className="p-8 flex flex-col h-full">
      <MenuPageHeader venue={venue} venueId={params.id} />
      <div className="flex-1 mt-6 min-h-0 overflow-hidden">
        <MenuEditor venueId={params.id} initialCategories={categories} initialDishes={dishes} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create frontend/apps/dashboard/components/menu/MenuPageHeader.tsx**

```tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import type { Venue } from "@/lib/api";
import DiffReview, { type DiffChange } from "./DiffReview";
import { applyParseDiff } from "@/lib/actions";

interface Props {
  venue: Venue;
  venueId: string;
}

export default function MenuPageHeader({ venue, venueId }: Props) {
  const [parsing, setParsing] = useState(false);
  const [diffChanges, setDiffChanges] = useState<DiffChange[] | null>(null);

  async function handleParse() {
    setParsing(true);
    const token = document.cookie.match(/(?:^|;\s*)token=([^;]+)/)?.[1] ?? "";
    const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      await fetch(`${API}/venues/${venueId}/reparse-diff`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const deadline = Date.now() + 60000;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 2000));
        const res = await fetch(`${API}/venues/${venueId}/parse-status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        if (data.status === "done") {
          setDiffChanges(data.diff_data ?? []);
          return;
        }
        if (data.status === "failed") {
          alert("Парсинг завершился с ошибкой: " + (data.error_message ?? ""));
          return;
        }
      }
      alert("Парсинг занял слишком долго");
    } catch {
      alert("Ошибка при запуске парсинга");
    } finally {
      setParsing(false);
    }
  }

  async function handleApplyDiff(selected: DiffChange[]) {
    await applyParseDiff(venueId, selected);
  }

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <nav className="text-sm text-gray-500 mb-1">
            <Link href="/venues" className="hover:text-orange-500">Заведения</Link>
            <span className="mx-2">/</span>
            <span className="text-gray-900">{venue.name}</span>
          </nav>
          <h1 className="text-2xl font-bold text-gray-900">Меню</h1>
        </div>
        {venue.parse_status !== "pending" && (
          <button
            onClick={handleParse}
            disabled={parsing}
            className="bg-gray-100 hover:bg-gray-200 disabled:opacity-60 text-gray-700 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {parsing ? "Парсим..." : "Обновить из источника"}
          </button>
        )}
      </div>
      {diffChanges !== null && (
        <DiffReview
          changes={diffChanges}
          onClose={() => setDiffChanges(null)}
          onApply={handleApplyDiff}
        />
      )}
    </>
  );
}
```

- [ ] **Step 3: Create frontend/apps/dashboard/components/menu/MenuEditor.tsx**

```tsx
"use client";

import { useState } from "react";
import type { Category, Dish } from "@/lib/api";
import CategoryEditor from "./CategoryEditor";
import DishRow from "./DishRow";

interface Props {
  venueId: string;
  initialCategories: Category[];
  initialDishes: Dish[];
}

export default function MenuEditor({ venueId, initialCategories, initialDishes }: Props) {
  const [activeCategoryId, setActiveCategoryId] = useState<string | null>(
    initialCategories[0]?.id ?? null
  );

  const activeDishes = initialDishes.filter((d) => d.category_id === activeCategoryId);

  return (
    <div className="flex gap-6 h-full overflow-hidden">
      <div className="w-64 flex-shrink-0 overflow-y-auto">
        <CategoryEditor
          venueId={venueId}
          categories={initialCategories}
          activeCategoryId={activeCategoryId}
          onSelectCategory={setActiveCategoryId}
        />
      </div>
      <div className="flex-1 overflow-y-auto">
        {activeCategoryId ? (
          activeDishes.length === 0 ? (
            <p className="text-gray-400 text-sm py-12 text-center">Нет блюд в этой категории</p>
          ) : (
            <div className="space-y-2 pb-8">
              {activeDishes.map((dish) => (
                <DishRow key={dish.id} dish={dish} venueId={venueId} />
              ))}
            </div>
          )
        ) : (
          <p className="text-gray-400 text-sm py-12 text-center">Выберите категорию</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create frontend/apps/dashboard/components/menu/CategoryEditor.tsx**

```tsx
"use client";

import { useState } from "react";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Category } from "@/lib/api";
import { reorderCategories } from "@/lib/actions";

function SortableItem({
  category,
  isActive,
  onSelect,
}: {
  category: Category;
  isActive: boolean;
  onSelect: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: category.id });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
        isActive ? "bg-orange-50 text-orange-600" : "hover:bg-gray-50 text-gray-700"
      }`}
    >
      <span {...attributes} {...listeners} className="text-gray-300 cursor-grab active:cursor-grabbing select-none text-xs">
        ⠿
      </span>
      <button onClick={onSelect} className="flex-1 text-left text-sm font-medium truncate">
        {category.name}
      </button>
    </div>
  );
}

interface Props {
  venueId: string;
  categories: Category[];
  activeCategoryId: string | null;
  onSelectCategory: (id: string) => void;
}

export default function CategoryEditor({ venueId, categories, activeCategoryId, onSelectCategory }: Props) {
  const [items, setItems] = useState(categories);
  const sensors = useSensors(useSensor(PointerSensor));

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = items.findIndex((c) => c.id === active.id);
    const newIndex = items.findIndex((c) => c.id === over.id);
    const reordered = arrayMove(items, oldIndex, newIndex);
    setItems(reordered);
    await reorderCategories(venueId, reordered.map((c) => c.id));
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-2">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-3 py-2">Категории</p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items.map((c) => c.id)} strategy={verticalListSortingStrategy}>
          {items.map((cat) => (
            <SortableItem
              key={cat.id}
              category={cat}
              isActive={cat.id === activeCategoryId}
              onSelect={() => onSelectCategory(cat.id)}
            />
          ))}
        </SortableContext>
      </DndContext>
    </div>
  );
}
```

- [ ] **Step 5: Create frontend/apps/dashboard/components/menu/DishRow.tsx**

```tsx
"use client";

import { useState } from "react";
import type { Dish } from "@/lib/api";
import { updateDishPrice, toggleDishAvailability } from "@/lib/actions";
import ImageUpload from "./ImageUpload";

export default function DishRow({ dish, venueId }: { dish: Dish; venueId: string }) {
  const [price, setPrice] = useState(dish.price);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(dish.price);
  const [available, setAvailable] = useState(dish.is_available);
  const [showUpload, setShowUpload] = useState(false);
  const [imageUrl, setImageUrl] = useState(dish.image_url);

  async function commitPrice() {
    setEditing(false);
    const p = parseFloat(draft);
    if (isNaN(p) || Math.abs(p - parseFloat(price)) < 0.001) return;
    const prev = price;
    setPrice(String(p));
    try {
      await updateDishPrice(venueId, dish.id, p);
    } catch {
      setPrice(prev);
    }
  }

  async function handleToggle() {
    const next = !available;
    setAvailable(next);
    try {
      await toggleDishAvailability(venueId, dish.id, next);
    } catch {
      setAvailable(!next);
    }
  }

  return (
    <>
      <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4">
        <button
          onClick={() => setShowUpload(true)}
          className="w-16 h-16 flex-shrink-0 rounded-lg overflow-hidden bg-gray-100 hover:opacity-75 transition-opacity"
          title="Изменить фото"
        >
          {imageUrl ? (
            <img src={imageUrl} alt={dish.name} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs">Фото</div>
          )}
        </button>

        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-900 text-sm">{dish.name}</p>
          {dish.description && <p className="text-gray-500 text-xs mt-0.5 line-clamp-1">{dish.description}</p>}
          {(dish.weight || dish.calories) && (
            <p className="text-gray-400 text-xs mt-0.5">{[dish.weight, dish.calories].filter(Boolean).join(" · ")}</p>
          )}
        </div>

        <div className="flex items-center gap-4 flex-shrink-0">
          {editing ? (
            <input
              autoFocus
              type="number"
              step="0.01"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={commitPrice}
              onKeyDown={(e) => e.key === "Enter" && commitPrice()}
              className="w-24 border border-orange-400 rounded-lg px-2 py-1 text-sm font-bold text-right outline-none focus:ring-2 focus:ring-orange-400"
            />
          ) : (
            <button
              onClick={() => { setDraft(price); setEditing(true); }}
              className="w-24 text-right text-sm font-bold text-gray-900 hover:text-orange-500 transition-colors"
              title="Нажмите для редактирования"
            >
              {Number(price).toLocaleString("ru-RU")} ₽
            </button>
          )}

          <label className="relative inline-flex items-center cursor-pointer" title={available ? "Доступно" : "Недоступно"}>
            <input type="checkbox" checked={available} onChange={handleToggle} className="sr-only peer" />
            <div className="w-9 h-5 bg-gray-200 rounded-full peer peer-checked:bg-orange-500 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4" />
          </label>
        </div>
      </div>

      {showUpload && (
        <ImageUpload
          venueId={venueId}
          dish={dish}
          onClose={() => setShowUpload(false)}
          onSuccess={(url) => setImageUrl(url)}
        />
      )}
    </>
  );
}
```

- [ ] **Step 6: Build to verify**

```bash
cd frontend/apps/dashboard && npm run build
```

Expected: Build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/apps/dashboard/app/\(dashboard\)/venues/ frontend/apps/dashboard/components/menu/
git commit -m "feat: menu editor with category dnd reorder and inline dish price/availability editing"
```

---

## Task 8: Dashboard — ImageUpload + DiffReview

**Files:**
- Create: `frontend/apps/dashboard/components/menu/ImageUpload.tsx`
- Create: `frontend/apps/dashboard/components/menu/DiffReview.tsx`

- [ ] **Step 1: Create frontend/apps/dashboard/components/menu/ImageUpload.tsx**

```tsx
"use client";

import { useState, useRef } from "react";
import ReactCrop, { type Crop, centerCrop, makeAspectCrop } from "react-image-crop";
import "react-image-crop/dist/ReactCrop.css";
import type { Dish } from "@/lib/api";
import { getUploadUrl, confirmDishImage } from "@/lib/actions";

interface Props {
  venueId: string;
  dish: Dish;
  onClose: () => void;
  onSuccess: (imageUrl: string) => void;
}

export default function ImageUpload({ venueId, dish, onClose, onSuccess }: Props) {
  const [src, setSrc] = useState<string>("");
  const [crop, setCrop] = useState<Crop>();
  const [uploading, setUploading] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setSrc(reader.result as string);
    reader.readAsDataURL(file);
  }

  function onImageLoad(e: React.SyntheticEvent<HTMLImageElement>) {
    const { naturalWidth: w, naturalHeight: h } = e.currentTarget;
    setCrop(centerCrop(makeAspectCrop({ unit: "%", width: 80 }, 1, w, h), w, h));
  }

  async function handleUpload() {
    if (!imgRef.current || !crop) return;
    setUploading(true);
    try {
      const img = imgRef.current;
      const scaleX = img.naturalWidth / img.width;
      const scaleY = img.naturalHeight / img.height;
      const canvas = document.createElement("canvas");
      canvas.width = 512;
      canvas.height = 512;
      canvas.getContext("2d")!.drawImage(
        img,
        (crop.x / 100) * img.width * scaleX,
        (crop.y / 100) * img.height * scaleY,
        (crop.width / 100) * img.width * scaleX,
        (crop.height / 100) * img.height * scaleY,
        0, 0, 512, 512
      );
      const blob = await new Promise<Blob>((res) => canvas.toBlob((b) => res(b!), "image/jpeg", 0.85));
      const { upload_url, image_url } = await getUploadUrl(venueId, dish.id);
      await fetch(upload_url, { method: "PUT", body: blob, headers: { "Content-Type": "image/jpeg" } });
      await confirmDishImage(venueId, dish.id, image_url);
      onSuccess(image_url);
      onClose();
    } catch {
      alert("Ошибка загрузки фото");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-gray-900">Фото: {dish.name}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>
        {!src ? (
          <label className="flex flex-col items-center justify-center h-32 border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:border-orange-400 transition-colors">
            <span className="text-sm text-gray-500 mb-1">Выберите фото</span>
            <span className="text-xs text-gray-400">JPG, PNG до 5 МБ</span>
            <input type="file" accept="image/*" onChange={onFile} className="hidden" />
          </label>
        ) : (
          <>
            <ReactCrop crop={crop} onChange={setCrop} aspect={1} className="max-h-72 rounded-lg overflow-hidden">
              <img ref={imgRef} src={src} onLoad={onImageLoad} alt="crop preview" className="max-w-full" />
            </ReactCrop>
            <div className="flex gap-3 mt-4">
              <button onClick={() => setSrc("")} className="flex-1 border border-gray-200 text-gray-700 py-2 rounded-lg text-sm font-medium hover:bg-gray-50">
                Другое фото
              </button>
              <button onClick={handleUpload} disabled={uploading} className="flex-1 bg-orange-500 text-white py-2 rounded-lg text-sm font-medium hover:bg-orange-600 disabled:opacity-60">
                {uploading ? "Загружаем..." : "Сохранить"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create frontend/apps/dashboard/components/menu/DiffReview.tsx**

```tsx
"use client";

import { useState } from "react";

export interface DiffChange {
  dish_id: string | null;
  action: "add" | "update" | "remove";
  name: string;
  old_price?: number;
  new_price?: number;
  old_weight?: string;
  new_weight?: string;
  description?: string;
}

interface Props {
  changes: DiffChange[];
  onClose: () => void;
  onApply: (selected: DiffChange[]) => Promise<void>;
}

export default function DiffReview({ changes, onClose, onApply }: Props) {
  const [selected, setSelected] = useState(() => new Set(changes.map((_, i) => i)));
  const [applying, setApplying] = useState(false);

  function toggle(i: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  }

  async function handleApply() {
    setApplying(true);
    try {
      await onApply(changes.filter((_, i) => selected.has(i)));
      onClose();
    } finally {
      setApplying(false);
    }
  }

  if (changes.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="bg-white rounded-2xl p-6 w-full max-w-md text-center">
          <p className="text-gray-500 text-sm">Изменений не обнаружено</p>
          <button onClick={onClose} className="mt-4 px-4 py-2 bg-gray-100 rounded-lg text-sm font-medium hover:bg-gray-200">
            Закрыть
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl p-6 w-full max-w-lg flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-gray-900">Изменения из источника</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>
        <div className="flex-1 overflow-y-auto space-y-1">
          {changes.map((change, i) => (
            <label key={i} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer">
              <input type="checkbox" checked={selected.has(i)} onChange={() => toggle(i)} className="mt-0.5 accent-orange-500" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">{change.name}</p>
                <div className="text-xs text-gray-500 mt-0.5">
                  {change.action === "add" && <span className="text-green-600">+ Новое · {change.new_price} ₽</span>}
                  {change.action === "remove" && <span className="text-red-500">− Удалено из источника</span>}
                  {change.action === "update" && (
                    <>
                      {change.old_price !== change.new_price && <span>Цена: {change.old_price} → {change.new_price} ₽ </span>}
                      {change.old_weight !== change.new_weight && <span>Вес: {change.old_weight} → {change.new_weight}</span>}
                    </>
                  )}
                </div>
              </div>
            </label>
          ))}
        </div>
        <div className="flex gap-3 mt-4 pt-4 border-t border-gray-100">
          <button onClick={onClose} className="flex-1 border border-gray-200 text-gray-700 py-2 rounded-lg text-sm font-medium hover:bg-gray-50">
            Отмена
          </button>
          <button onClick={handleApply} disabled={applying || selected.size === 0} className="flex-1 bg-orange-500 text-white py-2 rounded-lg text-sm font-medium hover:bg-orange-600 disabled:opacity-60">
            {applying ? "Применяем..." : `Принять (${selected.size})`}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Build to verify**

```bash
cd frontend/apps/dashboard && npm run build
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/dashboard/components/menu/ImageUpload.tsx frontend/apps/dashboard/components/menu/DiffReview.tsx
git commit -m "feat: image upload modal with crop, diff review modal for menu parser"
```

---

## Task 9: Dashboard — Tables & QR

**Files:**
- Create: `frontend/apps/dashboard/app/(dashboard)/venues/[id]/tables/page.tsx`
- Create: `frontend/apps/dashboard/components/tables/TableGrid.tsx`
- Create: `frontend/apps/dashboard/components/tables/QRPreview.tsx`

- [ ] **Step 1: Create frontend/apps/dashboard/app/(dashboard)/venues/[id]/tables/page.tsx**

```tsx
import Link from "next/link";
import { fetchTables, fetchVenue } from "@/lib/api";
import TableGrid from "@/components/tables/TableGrid";

interface Props {
  params: { id: string };
}

export default async function TablesPage({ params }: Props) {
  const [venue, { tables }] = await Promise.all([fetchVenue(params.id), fetchTables(params.id)]);
  return (
    <div className="p-8">
      <div className="mb-8">
        <nav className="text-sm text-gray-500 mb-1">
          <Link href="/venues" className="hover:text-orange-500">Заведения</Link>
          <span className="mx-2">/</span>
          <span className="text-gray-900">{venue.name}</span>
        </nav>
        <h1 className="text-2xl font-bold text-gray-900">Столы и QR-коды</h1>
      </div>
      <TableGrid venueId={params.id} initialTables={tables} />
    </div>
  );
}
```

- [ ] **Step 2: Create frontend/apps/dashboard/components/tables/TableGrid.tsx**

```tsx
"use client";

import { useState } from "react";
import type { Table } from "@/lib/api";
import QRPreview from "./QRPreview";

export default function TableGrid({ venueId, initialTables }: { venueId: string; initialTables: Table[] }) {
  const [tables, setTables] = useState(initialTables);
  const [generating, setGenerating] = useState(false);

  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  function getToken() {
    return document.cookie.match(/(?:^|;\s*)token=([^;]+)/)?.[1] ?? "";
  }

  async function handleGenerateQR() {
    setGenerating(true);
    try {
      await fetch(`${API}/venues/${venueId}/qr/generate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      await new Promise((r) => setTimeout(r, 3500));
      const res = await fetch(`${API}/venues/${venueId}/tables`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      const data = await res.json();
      setTables(data.tables);
    } finally {
      setGenerating(false);
    }
  }

  async function handleDownloadPDF() {
    const res = await fetch(`${API}/venues/${venueId}/qr/download`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `qr_${venueId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } else {
      alert("PDF ещё не сгенерирован. Нажмите «Перегенерировать QR» сначала.");
    }
  }

  return (
    <div>
      <div className="flex gap-3 mb-6">
        <button
          onClick={handleGenerateQR}
          disabled={generating}
          className="bg-orange-500 hover:bg-orange-600 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          {generating ? "Генерируем..." : "Перегенерировать QR"}
        </button>
        <button
          onClick={handleDownloadPDF}
          className="border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          Скачать PDF
        </button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {tables.map((table) => (
          <QRPreview key={table.id} table={table} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create frontend/apps/dashboard/components/tables/QRPreview.tsx**

```tsx
import type { Table } from "@/lib/api";

export default function QRPreview({ table }: { table: Table }) {
  const qrSrc = table.qr_code_url
    ? `https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${encodeURIComponent(table.qr_code_url)}`
    : null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-col items-center gap-3">
      <div className="w-28 h-28 flex items-center justify-center bg-gray-50 rounded-lg">
        {qrSrc ? (
          <img src={qrSrc} alt={`QR стол ${table.number}`} className="w-24 h-24" />
        ) : (
          <span className="text-gray-400 text-xs text-center px-2">QR не сгенерирован</span>
        )}
      </div>
      <div className="text-center">
        <p className="font-semibold text-gray-900 text-sm">{table.label ?? `Стол ${table.number}`}</p>
        <span className={`text-xs ${table.is_active ? "text-green-600" : "text-gray-400"}`}>
          {table.is_active ? "Активен" : "Неактивен"}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Build to verify**

```bash
cd frontend/apps/dashboard && npm run build
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/dashboard/app/\(dashboard\)/venues/\[id\]/tables/ frontend/apps/dashboard/components/tables/
git commit -m "feat: tables & QR management page with generate and download"
```

---

## Task 10: Dashboard — Analytics Page

**Files:**
- Create: `frontend/apps/dashboard/app/(dashboard)/venues/[id]/analytics/page.tsx`
- Create: `frontend/apps/dashboard/components/analytics/SummaryCards.tsx`
- Create: `frontend/apps/dashboard/components/analytics/PeriodFilter.tsx`
- Create: `frontend/apps/dashboard/components/analytics/RevenueChart.tsx`
- Create: `frontend/apps/dashboard/components/analytics/TopDishesChart.tsx`
- Create: `frontend/apps/dashboard/components/analytics/OrdersTable.tsx`

- [ ] **Step 1: Create frontend/apps/dashboard/components/analytics/SummaryCards.tsx**

```tsx
interface Summary {
  orders: number;
  revenue: string;
  avg_check: string;
  top_dish: string | null;
}

export default function SummaryCards({ summary }: { summary: Summary }) {
  const cards = [
    { label: "Заказов", value: summary.orders.toLocaleString("ru-RU") },
    { label: "Выручка", value: `${Number(summary.revenue).toLocaleString("ru-RU")} ₽` },
    { label: "Средний чек", value: `${Number(summary.avg_check).toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₽` },
    { label: "Топ блюдо", value: summary.top_dish ?? "—" },
  ];
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((c) => (
        <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500">{c.label}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1 truncate">{c.value}</p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create frontend/apps/dashboard/components/analytics/PeriodFilter.tsx**

```tsx
"use client";

import { useRouter, useSearchParams } from "next/navigation";

const PERIODS = [{ label: "7д", days: 7 }, { label: "30д", days: 30 }, { label: "90д", days: 90 }];

export default function PeriodFilter() {
  const router = useRouter();
  const sp = useSearchParams();
  const currentFrom = sp.get("from");

  function activeDays() {
    if (!currentFrom) return 30;
    return Math.round((Date.now() - new Date(currentFrom).getTime()) / 86400000);
  }

  function setPeriod(days: number) {
    const to = new Date().toISOString().split("T")[0];
    const from = new Date(Date.now() - days * 86400000).toISOString().split("T")[0];
    const next = new URLSearchParams(sp);
    next.set("from", from);
    next.set("to", to);
    router.push(`?${next}`);
  }

  const active = activeDays();
  return (
    <div className="flex gap-2">
      {PERIODS.map(({ label, days }) => (
        <button
          key={label}
          onClick={() => setPeriod(days)}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            active === days ? "bg-orange-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create frontend/apps/dashboard/components/analytics/RevenueChart.tsx**

```tsx
"use client";

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function RevenueChart({ data }: { data: Array<{ date: string; revenue: string; orders: number }> }) {
  if (data.length === 0) {
    return <div className="h-48 flex items-center justify-center text-gray-400 text-sm">Нет данных за период</div>;
  }
  const chartData = data.map((d) => ({ date: d.date.slice(5), revenue: Number(d.revenue), orders: d.orders }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={chartData}>
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#FF6B35" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#FF6B35" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#9ca3af" }} />
        <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} />
        <Tooltip formatter={(v: number, n: string) => [n === "revenue" ? `${v.toLocaleString("ru-RU")} ₽` : v, n === "revenue" ? "Выручка" : "Заказов"]} />
        <Area type="monotone" dataKey="revenue" stroke="#FF6B35" fill="url(#g)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 4: Create frontend/apps/dashboard/components/analytics/TopDishesChart.tsx**

```tsx
"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function TopDishesChart({ data }: { data: Array<{ name: string; count: number }> }) {
  if (data.length === 0) {
    return <div className="h-48 flex items-center justify-center text-gray-400 text-sm">Нет данных за период</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis type="number" tick={{ fontSize: 11, fill: "#9ca3af" }} />
        <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: "#6b7280" }} width={100} />
        <Tooltip formatter={(v: number) => [v, "Заказано"]} />
        <Bar dataKey="count" fill="#FF6B35" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 5: Create frontend/apps/dashboard/components/analytics/OrdersTable.tsx**

```tsx
"use client";

import { useState, useEffect } from "react";

const STATUSES = [
  { value: "", label: "Все статусы" },
  { value: "accepted", label: "Принят" },
  { value: "cooking", label: "Готовится" },
  { value: "ready", label: "Готов" },
  { value: "served", label: "Подан" },
  { value: "cancelled", label: "Отменён" },
];

const STATUS_STYLE: Record<string, string> = {
  accepted: "bg-blue-100 text-blue-700",
  cooking: "bg-yellow-100 text-yellow-700",
  ready: "bg-green-100 text-green-700",
  served: "bg-gray-100 text-gray-600",
  cancelled: "bg-red-100 text-red-600",
};

interface Order {
  id: string;
  status: string;
  total_amount: string;
  created_at: string;
  items: Array<{ id: string }>;
}

export default function OrdersTable({ venueId }: { venueId: string }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);

  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const LIMIT = 20;

  function getToken() {
    return document.cookie.match(/(?:^|;\s*)token=([^;]+)/)?.[1] ?? "";
  }

  useEffect(() => {
    const sp = new URLSearchParams({ page: String(page), limit: String(LIMIT) });
    if (status) sp.set("status", status);
    setLoading(true);
    fetch(`${API}/venues/${venueId}/orders?${sp}`, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((r) => r.json())
      .then((d) => { setOrders(d.orders ?? []); setTotal(d.total ?? 0); })
      .finally(() => setLoading(false));
  }, [page, status, venueId]);

  async function handleExportCSV() {
    const sp = new URLSearchParams({ format: "csv" });
    if (status) sp.set("status", status);
    const res = await fetch(`${API}/venues/${venueId}/orders?${sp}`, { headers: { Authorization: `Bearer ${getToken()}` } });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `orders_${venueId}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-orange-500"
        >
          {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <button onClick={handleExportCSV} className="ml-auto text-sm border border-gray-200 text-gray-600 px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors">
          Экспорт CSV
        </button>
      </div>

      {loading ? (
        <div className="py-10 text-center text-gray-400 text-sm">Загрузка...</div>
      ) : orders.length === 0 ? (
        <div className="py-10 text-center text-gray-400 text-sm">Заказов нет</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-gray-500 font-medium">
                <th className="text-left py-3 px-2">Дата и время</th>
                <th className="text-left py-3 px-2">Статус</th>
                <th className="text-right py-3 px-2">Сумма</th>
                <th className="text-right py-3 px-2">Позиций</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 px-2 text-gray-600">
                    {new Date(order.created_at).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                  </td>
                  <td className="py-3 px-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLE[order.status] ?? "bg-gray-100 text-gray-600"}`}>
                      {STATUSES.find((s) => s.value === order.status)?.label ?? order.status}
                    </span>
                  </td>
                  <td className="py-3 px-2 text-right font-medium text-gray-900">
                    {Number(order.total_amount).toLocaleString("ru-RU")} ₽
                  </td>
                  <td className="py-3 px-2 text-right text-gray-500">{order.items.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center gap-2 mt-4">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50">
            ← Назад
          </button>
          <span className="text-sm text-gray-500">Стр. {page} из {totalPages}</span>
          <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50">
            Вперёд →
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Create frontend/apps/dashboard/app/(dashboard)/venues/[id]/analytics/page.tsx**

```tsx
import Link from "next/link";
import { fetchAnalytics, fetchVenue } from "@/lib/api";
import SummaryCards from "@/components/analytics/SummaryCards";
import RevenueChart from "@/components/analytics/RevenueChart";
import TopDishesChart from "@/components/analytics/TopDishesChart";
import OrdersTable from "@/components/analytics/OrdersTable";
import PeriodFilter from "@/components/analytics/PeriodFilter";

interface Props {
  params: { id: string };
  searchParams: { from?: string; to?: string };
}

export default async function AnalyticsPage({ params, searchParams }: Props) {
  const [venue, analytics] = await Promise.all([
    fetchVenue(params.id),
    fetchAnalytics(params.id, searchParams.from, searchParams.to),
  ]);
  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <nav className="text-sm text-gray-500 mb-1">
            <Link href="/venues" className="hover:text-orange-500">Заведения</Link>
            <span className="mx-2">/</span>
            <span className="text-gray-900">{venue.name}</span>
          </nav>
          <h1 className="text-2xl font-bold text-gray-900">Аналитика</h1>
        </div>
        <PeriodFilter />
      </div>

      <SummaryCards summary={analytics.summary} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Выручка по дням</h2>
          <RevenueChart data={analytics.daily} />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Топ блюд</h2>
          <TopDishesChart data={analytics.top_dishes} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-4">История заказов</h2>
        <OrdersTable venueId={params.id} />
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Final build**

```bash
cd frontend/apps/dashboard && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 8: Run full backend test suite one more time**

```bash
cd backend && python3 -m pytest tests/ -v --tb=short
```

Expected: All tests PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/apps/dashboard/components/analytics/ frontend/apps/dashboard/app/\(dashboard\)/venues/\[id\]/analytics/
git commit -m "feat: analytics page — summary cards, revenue chart, top dishes, orders table with pagination and CSV export"
```
