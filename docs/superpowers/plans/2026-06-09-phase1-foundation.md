# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Рабочий backend с Auth API, парсером меню и генератором QR PDF — владелец регистрируется, вводит URL сайта, получает PDF с QR-кодами.

**Architecture:** FastAPI-монолит с отдельными Worker-процессами для парсера и QR-генератора. PostgreSQL — основная БД, Redis — Pub/Sub и кэш. Все сервисы запускаются через Docker Compose. Тесты используют отдельную тестовую БД, запускаются через pytest + httpx.

**Tech Stack:** FastAPI, SQLAlchemy 2 (async), asyncpg, Alembic, Redis (aioredis), BeautifulSoup4, Playwright, qrcode, ReportLab, boto3 (S3), pytest, pytest-asyncio, httpx

---

## Файловая структура

```
menuscan/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── core/
│   │   │   ├── config.py            # pydantic-settings: ENV vars
│   │   │   ├── security.py          # JWT encode/decode, password hash
│   │   │   └── deps.py              # FastAPI dependencies (get_db, get_current_user)
│   │   ├── models/
│   │   │   ├── base.py              # Base declarative, common timestamps mixin
│   │   │   ├── user.py
│   │   │   ├── venue.py
│   │   │   ├── table.py
│   │   │   ├── category.py
│   │   │   ├── dish.py
│   │   │   ├── order.py
│   │   │   ├── parse_job.py
│   │   │   ├── qr_batch.py
│   │   │   └── subscription.py
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── venue.py
│   │   │   ├── table.py
│   │   │   ├── dish.py
│   │   │   └── common.py            # общие типы (UUIDModel, etc.)
│   │   ├── api/
│   │   │   ├── router.py            # подключает все sub-роутеры
│   │   │   ├── auth.py
│   │   │   ├── venues.py
│   │   │   ├── tables.py
│   │   │   ├── dishes.py
│   │   │   └── menu.py              # публичное меню для гостей
│   │   ├── services/
│   │   │   ├── auth.py              # register, login logic
│   │   │   ├── venue.py             # создание venue + запуск parse job
│   │   │   └── qr.py               # генерация QR + сборка PDF
│   │   └── workers/
│   │       └── parser.py            # парсер меню (BS4 + Playwright)
│   ├── alembic/
│   │   ├── versions/
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── tests/
│   │   ├── conftest.py              # fixtures: db, client, test user
│   │   ├── test_auth.py
│   │   ├── test_venues.py
│   │   ├── test_dishes.py
│   │   ├── test_parser.py
│   │   └── test_qr.py
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── .env.example
├── .github/
│   └── workflows/
│       └── ci.yml
├── docker-compose.yml
├── docker-compose.prod.yml
└── CLAUDE.md
```

---

## Task 1: Инфраструктура — Docker Compose + pyproject.toml

**Files:**
- Create: `docker-compose.yml`
- Create: `docker-compose.prod.yml`
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/Dockerfile`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Создать docker-compose.yml**

```yaml
# docker-compose.yml
version: "3.9"

services:
  api:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    env_file: ./backend/.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: menuscan
      POSTGRES_PASSWORD: menuscan
      POSTGRES_DB: menuscan
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U menuscan"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

- [ ] **Step 2: Создать backend/pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "menuscan-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pydantic[email]>=2.7.0",
    "pydantic-settings>=2.3.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.9",
    "redis[hiredis]>=5.0.0",
    "beautifulsoup4>=4.12.0",
    "requests>=2.32.0",
    "playwright>=1.44.0",
    "qrcode[pil]>=7.4.2",
    "reportlab>=4.2.0",
    "boto3>=1.34.0",
    "pillow>=10.3.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "anyio>=4.4.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 3: Создать backend/.env.example**

```env
# Database
DATABASE_URL=postgresql+asyncpg://menuscan:menuscan@localhost:5432/menuscan
TEST_DATABASE_URL=postgresql+asyncpg://menuscan:menuscan@localhost:5432/menuscan_test

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=change-me-in-production-use-openssl-rand-hex-32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# S3 (MinIO local)
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=menuscan

# App
APP_ENV=development
MENU_BASE_URL=http://localhost:3001
```

- [ ] **Step 4: Создать backend/Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8000
```

- [ ] **Step 5: Создать backend/app/main.py**

```python
from fastapi import FastAPI
from app.api.router import api_router

app = FastAPI(title="MenuScan API", version="0.1.0")

app.include_router(api_router, prefix="/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Создать backend/app/api/router.py** (заглушка, будем расширять)

```python
from fastapi import APIRouter

api_router = APIRouter()
```

- [ ] **Step 7: Запустить инфраструктуру и проверить**

```bash
cd /path/to/menuscan
docker-compose up -d postgres redis minio
docker-compose ps
```

Ожидаем: все три сервиса `healthy`.

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
curl http://localhost:8000/health
```

Ожидаем: `{"status": "ok"}`

- [ ] **Step 8: Commit**

```bash
git add docker-compose.yml docker-compose.prod.yml backend/
git commit -m "feat: project scaffold — Docker Compose, FastAPI skeleton, pyproject.toml"
```

---

## Task 2: Core config + database models + Alembic

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/venue.py`
- Create: `backend/app/models/table.py`
- Create: `backend/app/models/category.py`
- Create: `backend/app/models/dish.py`
- Create: `backend/app/models/order.py`
- Create: `backend/app/models/parse_job.py`
- Create: `backend/app/models/qr_batch.py`
- Create: `backend/app/models/subscription.py`
- Create: `backend/alembic/env.py`

- [ ] **Step 1: Создать backend/app/core/config.py**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    TEST_DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "menuscan"

    MENU_BASE_URL: str = "http://localhost:3001"
    APP_ENV: str = "development"


settings = Settings()
```

- [ ] **Step 2: Создать backend/app/models/base.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def gen_uuid() -> uuid.UUID:
    return uuid.uuid4()
```

- [ ] **Step 3: Создать backend/app/models/user.py**

```python
import uuid
from sqlalchemy import String, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin, gen_uuid


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="owner")

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin')", name="users_role_check"),
    )

    venues: Mapped[list["Venue"]] = relationship(back_populates="owner")
```

- [ ] **Step 4: Создать backend/app/models/venue.py**

```python
import uuid
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, TimestampMixin, gen_uuid


class Venue(Base, TimestampMixin):
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    cuisine_type: Mapped[str | None] = mapped_column(String(100))
    logo_url: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(50), default="pending")
    table_count: Mapped[int] = mapped_column(Integer, default=0)
    timezone: Mapped[str] = mapped_column(String(100), default="Europe/Moscow")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        CheckConstraint(
            "parse_status IN ('pending','parsing','done','failed','manual')",
            name="venues_parse_status_check",
        ),
    )

    owner: Mapped["User"] = relationship(back_populates="venues")
    tables: Mapped[list["Table"]] = relationship(back_populates="venue", cascade="all, delete-orphan")
    categories: Mapped[list["Category"]] = relationship(back_populates="venue", cascade="all, delete-orphan")
    dishes: Mapped[list["Dish"]] = relationship(back_populates="venue", cascade="all, delete-orphan")
    parse_jobs: Mapped[list["ParseJob"]] = relationship(back_populates="venue", cascade="all, delete-orphan")
    subscription: Mapped["Subscription | None"] = relationship(back_populates="venue", uselist=False)
```

- [ ] **Step 5: Создать backend/app/models/table.py**

```python
import uuid
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, gen_uuid
from datetime import datetime
from sqlalchemy import DateTime, func


class Table(Base):
    __tablename__ = "tables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    qr_code_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("venue_id", "number", name="tables_venue_number_uc"),)

    venue: Mapped["Venue"] = relationship(back_populates="tables")
```

- [ ] **Step 6: Создать backend/app/models/category.py**

```python
import uuid
from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, gen_uuid
from datetime import datetime


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("venue_id", "slug", name="categories_venue_slug_uc"),)

    venue: Mapped["Venue"] = relationship(back_populates="categories")
    dishes: Mapped[list["Dish"]] = relationship(back_populates="category")
```

- [ ] **Step 7: Создать backend/app/models/dish.py**

```python
import uuid
from decimal import Decimal
from sqlalchemy import String, Text, Numeric, Integer, Boolean, ForeignKey, Index, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, TimestampMixin, gen_uuid


class Dish(Base, TimestampMixin):
    __tablename__ = "dishes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    weight: Mapped[str | None] = mapped_column(String(50))
    calories: Mapped[str | None] = mapped_column(String(50))
    image_url: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    allergens: Mapped[list] = mapped_column(JSONB, default=list)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("idx_dishes_venue_id", "venue_id"),
        Index("idx_dishes_category_id", "category_id"),
        Index("idx_dishes_tags", "tags", postgresql_using="gin"),
    )

    venue: Mapped["Venue"] = relationship(back_populates="dishes")
    category: Mapped["Category | None"] = relationship(back_populates="dishes")
```

- [ ] **Step 8: Создать backend/app/models/order.py**

```python
import uuid
from decimal import Decimal
from sqlalchemy import String, Text, Numeric, Integer, ForeignKey, CheckConstraint, Index, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin, gen_uuid


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id"))
    table_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tables.id"))
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="accepted")
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    comment: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN ('accepted','cooking','ready','served','cancelled')",
            name="orders_status_check",
        ),
        Index("idx_orders_venue_id", "venue_id"),
        Index("idx_orders_table_id", "table_id"),
        Index("idx_orders_status", "status"),
    )

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"))
    dish_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dishes.id"))
    guest_id: Mapped[str] = mapped_column(String(100), nullable=False)
    guest_name: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="items")
```

- [ ] **Step 9: Создать backend/app/models/parse_job.py и qr_batch.py и subscription.py**

```python
# app/models/parse_job.py
import uuid
from sqlalchemy import String, Text, Integer, ForeignKey, CheckConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, gen_uuid
from datetime import datetime


class ParseJob(Base):
    __tablename__ = "parse_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(50), default="queued")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    dishes_found: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('queued','running','done','failed')", name="parse_jobs_status_check"),
    )

    venue: Mapped["Venue"] = relationship(back_populates="parse_jobs")
```

```python
# app/models/qr_batch.py
import uuid
from sqlalchemy import Text, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, gen_uuid
from datetime import datetime


class QrBatch(Base):
    __tablename__ = "qr_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"))
    table_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

```python
# app/models/subscription.py
import uuid
from sqlalchemy import String, ForeignKey, CheckConstraint, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, gen_uuid
from datetime import datetime


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"))
    plan: Mapped[str] = mapped_column(String(50), default="starter")
    status: Mapped[str] = mapped_column(String(50), default="trial")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_provider_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("plan IN ('starter','business','pro','enterprise')", name="sub_plan_check"),
        CheckConstraint("status IN ('trial','active','past_due','cancelled')", name="sub_status_check"),
        UniqueConstraint("venue_id", name="subscriptions_venue_id_uc"),
    )

    venue: Mapped["Venue"] = relationship(back_populates="subscription")
```

- [ ] **Step 10: Настроить Alembic**

```bash
cd backend
alembic init alembic
```

Заменить содержимое `alembic/env.py`:

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.core.config import settings
from app.models.base import Base
# импортируем все модели, чтобы Alembic их увидел
from app.models import user, venue, table, category, dish, order, parse_job, qr_batch, subscription  # noqa

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 11: Создать и применить первую миграцию**

```bash
cd backend
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

Ожидаем: все таблицы созданы без ошибок.

```bash
# Проверить через psql
docker exec -it menuscan-postgres-1 psql -U menuscan -c "\dt"
```

Ожидаем: 10 таблиц (users, venues, tables, categories, dishes, orders, order_items, parse_jobs, qr_batches, subscriptions).

- [ ] **Step 12: Commit**

```bash
git add backend/
git commit -m "feat: SQLAlchemy models + Alembic initial schema — all 10 tables"
```

---

## Task 3: Security + Dependencies (JWT, password hashing)

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/core/deps.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Создать backend/app/core/security.py**

```python
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": subject, "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
```

- [ ] **Step 2: Написать тест на security**

```python
# tests/test_security.py
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token


def test_password_hash_and_verify():
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip():
    token = create_access_token("user-uuid-123")
    subject = decode_access_token(token)
    assert subject == "user-uuid-123"


def test_jwt_invalid_token_returns_none():
    assert decode_access_token("not.a.valid.token") is None
```

- [ ] **Step 3: Запустить тест и убедиться, что проходит**

```bash
cd backend
pytest tests/test_security.py -v
```

Ожидаем: 3 теста PASSED.

- [ ] **Step 4: Создать backend/app/core/deps.py**

```python
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.user import User
from sqlalchemy import select

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

bearer_scheme = HTTPBearer()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

- [ ] **Step 5: Создать backend/tests/conftest.py**

```python
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.core.deps import get_db
from app.models.base import Base
from app.core.config import settings

TEST_DB_URL = settings.TEST_DATABASE_URL or settings.DATABASE_URL.replace("/menuscan", "/menuscan_test")

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db() -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncClient:
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

- [ ] **Step 6: Создать тестовую БД**

```bash
docker exec -it menuscan-postgres-1 psql -U menuscan -c "CREATE DATABASE menuscan_test;"
```

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: JWT security, password hashing, DB session deps, test fixtures"
```

---

## Task 4: Auth API (register, login, refresh)

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/auth.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Написать тесты на auth**

```python
# tests/test_auth.py
import pytest
from httpx import AsyncClient


async def test_register_success(client: AsyncClient):
    resp = await client.post("/v1/auth/register", json={
        "email": "owner@test.ru",
        "password": "StrongPass123",
        "full_name": "Тест Тестов",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == "owner@test.ru"
    assert "access_token" in data


async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dup@test.ru", "password": "Pass123", "full_name": "Dup"}
    await client.post("/v1/auth/register", json=payload)
    resp = await client.post("/v1/auth/register", json=payload)
    assert resp.status_code == 409


async def test_login_success(client: AsyncClient):
    await client.post("/v1/auth/register", json={
        "email": "login@test.ru", "password": "Pass123", "full_name": "L"
    })
    resp = await client.post("/v1/auth/login", json={"email": "login@test.ru", "password": "Pass123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_wrong_password(client: AsyncClient):
    await client.post("/v1/auth/register", json={
        "email": "wp@test.ru", "password": "Pass123", "full_name": "W"
    })
    resp = await client.post("/v1/auth/login", json={"email": "wp@test.ru", "password": "wrong"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Запустить — убедиться что FAIL (роутер не подключён)**

```bash
pytest tests/test_auth.py -v
```

Ожидаем: 4 теста FAILED с 404.

- [ ] **Step 3: Создать backend/app/schemas/auth.py**

```python
from pydantic import BaseModel, EmailStr
import uuid


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400


class RegisterResponse(BaseModel):
    user: UserOut
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 4: Создать backend/app/services/auth.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token
from app.schemas.auth import RegisterRequest


async def register_user(db: AsyncSession, payload: RegisterRequest) -> tuple[User, str]:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(str(user.id))
    return user, token


async def login_user(db: AsyncSession, email: str, password: str) -> tuple[User, str]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(str(user.id))
    return user, token
```

- [ ] **Step 5: Создать backend/app/api/auth.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user
from app.core.security import create_access_token
from app.schemas.auth import RegisterRequest, LoginRequest, RegisterResponse, TokenResponse, UserOut
from app.services.auth import register_user, login_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user, token = await register_user(db, payload)
    return RegisterResponse(user=UserOut.model_validate(user), access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    _, token = await login_user(db, payload.email, payload.password)
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(current_user: User = Depends(get_current_user)):
    token = create_access_token(str(current_user.id))
    return TokenResponse(access_token=token)
```

- [ ] **Step 6: Подключить роутер в backend/app/api/router.py**

```python
from fastapi import APIRouter
from app.api.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)
```

- [ ] **Step 7: Запустить тесты — убедиться PASS**

```bash
pytest tests/test_auth.py -v
```

Ожидаем: 4 теста PASSED.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: Auth API — register, login, refresh with JWT"
```

---

## Task 5: Venues + Tables CRUD API

**Files:**
- Create: `backend/app/schemas/venue.py`
- Create: `backend/app/services/venue.py`
- Create: `backend/app/api/venues.py`
- Create: `backend/app/api/tables.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_venues.py`

- [ ] **Step 1: Написать тесты**

```python
# tests/test_venues.py
import pytest
from httpx import AsyncClient


async def _get_token(client: AsyncClient) -> str:
    await client.post("/v1/auth/register", json={
        "email": "venue_owner@test.ru", "password": "Pass123", "full_name": "Owner"
    })
    resp = await client.post("/v1/auth/login", json={"email": "venue_owner@test.ru", "password": "Pass123"})
    return resp.json()["access_token"]


async def test_create_venue(client: AsyncClient):
    token = await _get_token(client)
    resp = await client.post("/v1/venues", json={
        "name": "Кафе Белуга",
        "website_url": "https://beluga.ru/menu",
        "table_count": 5,
        "address": "Москва",
        "cuisine_type": "Европейская",
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 202
    data = resp.json()
    assert data["venue"]["name"] == "Кафе Белуга"
    assert data["venue"]["slug"] == "kafe-beluga"
    assert data["venue"]["parse_status"] == "pending"


async def test_get_venues_list(client: AsyncClient):
    token = await _get_token(client)
    await client.post("/v1/venues", json={
        "name": "Ресторан Тест", "website_url": "https://test.ru", "table_count": 3
    }, headers={"Authorization": f"Bearer {token}"})
    resp = await client.get("/v1/venues", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()["venues"]) >= 1


async def test_get_venue_tables(client: AsyncClient):
    token = await _get_token(client)
    create_resp = await client.post("/v1/venues", json={
        "name": "С Столами", "website_url": "https://s.ru", "table_count": 4
    }, headers={"Authorization": f"Bearer {token}"})
    venue_id = create_resp.json()["venue"]["id"]
    resp = await client.get(f"/v1/venues/{venue_id}/tables", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()["tables"]) == 4


async def test_create_venue_unauthorized(client: AsyncClient):
    resp = await client.post("/v1/venues", json={"name": "X", "table_count": 1})
    assert resp.status_code == 403
```

- [ ] **Step 2: Запустить — убедиться FAIL**

```bash
pytest tests/test_venues.py -v
```

- [ ] **Step 3: Создать backend/app/schemas/venue.py**

```python
import uuid
from pydantic import BaseModel


class VenueCreate(BaseModel):
    name: str
    website_url: str | None = None
    table_count: int = 0
    address: str | None = None
    cuisine_type: str | None = None


class VenueUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    cuisine_type: str | None = None
    settings: dict | None = None
    is_active: bool | None = None


class VenueOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    table_count: int
    parse_status: str
    is_active: bool

    model_config = {"from_attributes": True}


class VenueDetail(VenueOut):
    address: str | None
    cuisine_type: str | None
    logo_url: str | None
    website_url: str | None
    settings: dict
    created_at: object


class TableOut(BaseModel):
    id: uuid.UUID
    number: int
    label: str | None
    qr_code_url: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class TableUpdate(BaseModel):
    label: str | None = None
    is_active: bool | None = None
```

- [ ] **Step 4: Создать backend/app/services/venue.py**

```python
import re
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.venue import Venue
from app.models.table import Table
from app.models.user import User
from app.schemas.venue import VenueCreate, VenueUpdate


def _slugify(name: str) -> str:
    name = name.lower()
    transliteration = str.maketrans("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", "abvgdeejzijklmnoprstufhcchshh_y_eua")
    name = name.translate(transliteration)
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-")


async def _unique_slug(db: AsyncSession, base_slug: str) -> str:
    slug = base_slug
    i = 1
    while True:
        result = await db.execute(select(Venue).where(Venue.slug == slug))
        if not result.scalar_one_or_none():
            return slug
        slug = f"{base_slug}-{i}"
        i += 1


async def create_venue(db: AsyncSession, payload: VenueCreate, owner: User) -> Venue:
    slug = await _unique_slug(db, _slugify(payload.name))
    venue = Venue(
        owner_id=owner.id,
        name=payload.name,
        slug=slug,
        website_url=payload.website_url,
        table_count=payload.table_count,
        address=payload.address,
        cuisine_type=payload.cuisine_type,
        parse_status="pending",
    )
    db.add(venue)
    await db.flush()
    for n in range(1, payload.table_count + 1):
        db.add(Table(venue_id=venue.id, number=n, label=f"Стол {n}"))
    await db.commit()
    await db.refresh(venue)
    return venue


async def get_owner_venues(db: AsyncSession, owner_id: uuid.UUID) -> list[Venue]:
    result = await db.execute(select(Venue).where(Venue.owner_id == owner_id))
    return list(result.scalars().all())


async def get_venue_or_404(db: AsyncSession, venue_id: uuid.UUID, owner_id: uuid.UUID) -> Venue:
    from fastapi import HTTPException
    result = await db.execute(
        select(Venue).where(Venue.id == venue_id, Venue.owner_id == owner_id)
    )
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


async def update_venue(db: AsyncSession, venue: Venue, payload: VenueUpdate) -> Venue:
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(venue, field, value)
    await db.commit()
    await db.refresh(venue)
    return venue
```

- [ ] **Step 5: Создать backend/app/api/venues.py**

```python
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.table import Table
from app.schemas.venue import VenueCreate, VenueUpdate, VenueOut, VenueDetail, TableOut, TableUpdate
from app.services.venue import create_venue, get_owner_venues, get_venue_or_404, update_venue

router = APIRouter(prefix="/venues", tags=["venues"])


@router.post("", status_code=202)
async def create(
    payload: VenueCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    venue = await create_venue(db, payload, current_user)
    return {"venue": VenueOut.model_validate(venue), "parse_job_id": None}


@router.get("")
async def list_venues(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    venues = await get_owner_venues(db, current_user.id)
    return {"venues": [VenueOut.model_validate(v) for v in venues]}


@router.get("/{venue_id}")
async def get_venue(
    venue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    venue = await get_venue_or_404(db, venue_id, current_user.id)
    return VenueDetail.model_validate(venue)


@router.patch("/{venue_id}")
async def patch_venue(
    venue_id: uuid.UUID,
    payload: VenueUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    venue = await get_venue_or_404(db, venue_id, current_user.id)
    venue = await update_venue(db, venue, payload)
    return VenueDetail.model_validate(venue)


@router.get("/{venue_id}/tables")
async def list_tables(
    venue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, current_user.id)
    result = await db.execute(select(Table).where(Table.venue_id == venue_id).order_by(Table.number))
    tables = result.scalars().all()
    return {"tables": [TableOut.model_validate(t) for t in tables]}


@router.patch("/{venue_id}/tables/{table_id}")
async def patch_table(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    payload: TableUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, current_user.id)
    result = await db.execute(select(Table).where(Table.id == table_id, Table.venue_id == venue_id))
    table = result.scalar_one_or_none()
    if not table:
        from fastapi import HTTPException
        raise HTTPException(404, "Table not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(table, field, value)
    await db.commit()
    await db.refresh(table)
    return TableOut.model_validate(table)
```

- [ ] **Step 6: Обновить backend/app/api/router.py**

```python
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.venues import router as venues_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(venues_router)
```

- [ ] **Step 7: Запустить тесты**

```bash
pytest tests/test_venues.py -v
```

Ожидаем: 4 теста PASSED.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: Venues + Tables CRUD API with ownership check"
```

---

## Task 6: Categories + Dishes CRUD API

**Files:**
- Create: `backend/app/schemas/dish.py`
- Create: `backend/app/api/dishes.py`
- Create: `backend/app/api/menu.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_dishes.py`

- [ ] **Step 1: Написать тесты**

```python
# tests/test_dishes.py
import pytest
from httpx import AsyncClient


async def _setup(client: AsyncClient) -> tuple[str, str]:
    """Возвращает (token, venue_id)"""
    await client.post("/v1/auth/register", json={
        "email": "dish_owner@test.ru", "password": "Pass123", "full_name": "D"
    })
    login = await client.post("/v1/auth/login", json={"email": "dish_owner@test.ru", "password": "Pass123"})
    token = login.json()["access_token"]
    venue_resp = await client.post("/v1/venues", json={
        "name": "Блюдо Кафе", "table_count": 2
    }, headers={"Authorization": f"Bearer {token}"})
    venue_id = venue_resp.json()["venue"]["id"]
    return token, venue_id


async def test_create_dish(client: AsyncClient):
    token, venue_id = await _setup(client)
    resp = await client.post(f"/v1/venues/{venue_id}/dishes", json={
        "name": "Капучино",
        "price": 220.0,
        "weight": "300мл",
        "tags": ["vegetarian"],
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Капучино"
    assert float(data["price"]) == 220.0


async def test_list_dishes(client: AsyncClient):
    token, venue_id = await _setup(client)
    await client.post(f"/v1/venues/{venue_id}/dishes", json={
        "name": "Эспрессо", "price": 150.0
    }, headers={"Authorization": f"Bearer {token}"})
    resp = await client.get(f"/v1/venues/{venue_id}/dishes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()["dishes"]) >= 1


async def test_patch_dish(client: AsyncClient):
    token, venue_id = await _setup(client)
    create = await client.post(f"/v1/venues/{venue_id}/dishes", json={
        "name": "Латте", "price": 250.0
    }, headers={"Authorization": f"Bearer {token}"})
    dish_id = create.json()["id"]
    resp = await client.patch(f"/v1/venues/{venue_id}/dishes/{dish_id}", json={
        "price": 270.0, "is_available": False
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert float(resp.json()["price"]) == 270.0
    assert resp.json()["is_available"] is False


async def test_public_menu(client: AsyncClient):
    token, venue_id = await _setup(client)
    venue_resp = await client.get(f"/v1/venues/{venue_id}", headers={"Authorization": f"Bearer {token}"})
    slug = venue_resp.json()["slug"]
    await client.post(f"/v1/venues/{venue_id}/dishes", json={
        "name": "Чай", "price": 100.0
    }, headers={"Authorization": f"Bearer {token}"})
    resp = await client.get(f"/v1/menu/{slug}")
    assert resp.status_code == 200
    assert resp.json()["venue"]["name"] == "Блюдо Кафе"
```

- [ ] **Step 2: Запустить — убедиться FAIL**

```bash
pytest tests/test_dishes.py -v
```

- [ ] **Step 3: Создать backend/app/schemas/dish.py**

```python
import uuid
from decimal import Decimal
from pydantic import BaseModel


class DishCreate(BaseModel):
    name: str
    description: str | None = None
    price: Decimal
    weight: str | None = None
    calories: str | None = None
    category_id: uuid.UUID | None = None
    tags: list[str] = []
    allergens: list[str] = []


class DishUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: Decimal | None = None
    weight: str | None = None
    calories: str | None = None
    category_id: uuid.UUID | None = None
    tags: list[str] | None = None
    allergens: list[str] | None = None
    is_available: bool | None = None
    sort_order: int | None = None


class DishOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    weight: str | None
    calories: str | None
    image_url: str | None
    tags: list
    allergens: list
    is_available: bool
    category_id: uuid.UUID | None

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Создать backend/app/api/dishes.py**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.dish import Dish
from app.schemas.dish import DishCreate, DishUpdate, DishOut
from app.services.venue import get_venue_or_404

router = APIRouter(tags=["dishes"])


@router.post("/venues/{venue_id}/dishes", response_model=DishOut, status_code=201)
async def create_dish(
    venue_id: uuid.UUID,
    payload: DishCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, current_user.id)
    dish = Dish(venue_id=venue_id, **payload.model_dump())
    db.add(dish)
    await db.commit()
    await db.refresh(dish)
    return dish


@router.get("/venues/{venue_id}/dishes")
async def list_dishes(
    venue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, current_user.id)
    result = await db.execute(select(Dish).where(Dish.venue_id == venue_id).order_by(Dish.sort_order))
    return {"dishes": [DishOut.model_validate(d) for d in result.scalars().all()]}


@router.patch("/venues/{venue_id}/dishes/{dish_id}", response_model=DishOut)
async def patch_dish(
    venue_id: uuid.UUID,
    dish_id: uuid.UUID,
    payload: DishUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, current_user.id)
    result = await db.execute(select(Dish).where(Dish.id == dish_id, Dish.venue_id == venue_id))
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(404, "Dish not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(dish, field, value)
    await db.commit()
    await db.refresh(dish)
    return dish


@router.delete("/venues/{venue_id}/dishes/{dish_id}", status_code=204)
async def delete_dish(
    venue_id: uuid.UUID,
    dish_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, current_user.id)
    result = await db.execute(select(Dish).where(Dish.id == dish_id, Dish.venue_id == venue_id))
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(404, "Dish not found")
    await db.delete(dish)
    await db.commit()
```

- [ ] **Step 5: Создать backend/app/api/menu.py (публичное меню)**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.deps import get_db
from app.models.venue import Venue
from app.models.category import Category
from app.models.dish import Dish
from app.schemas.dish import DishOut

router = APIRouter(tags=["menu"])


@router.get("/menu/{venue_slug}")
async def get_menu(venue_slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Venue).where(Venue.slug == venue_slug, Venue.is_active == True))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(404, "Venue not found")

    cats_result = await db.execute(
        select(Category).where(Category.venue_id == venue.id, Category.is_visible == True).order_by(Category.sort_order)
    )
    categories = cats_result.scalars().all()

    dishes_result = await db.execute(
        select(Dish).where(Dish.venue_id == venue.id, Dish.is_available == True).order_by(Dish.sort_order)
    )
    all_dishes = dishes_result.scalars().all()
    dishes_by_cat: dict = {}
    uncategorized = []
    for d in all_dishes:
        if d.category_id:
            dishes_by_cat.setdefault(str(d.category_id), []).append(d)
        else:
            uncategorized.append(d)

    cats_out = []
    for cat in categories:
        cats_out.append({
            "id": str(cat.id),
            "name": cat.name,
            "slug": cat.slug,
            "sort_order": cat.sort_order,
            "dishes": [DishOut.model_validate(d) for d in dishes_by_cat.get(str(cat.id), [])],
        })
    if uncategorized:
        cats_out.append({
            "id": None,
            "name": "Остальное",
            "slug": "other",
            "sort_order": 9999,
            "dishes": [DishOut.model_validate(d) for d in uncategorized],
        })

    return {
        "venue": {
            "id": str(venue.id),
            "name": venue.name,
            "logo_url": venue.logo_url,
            "settings": venue.settings,
        },
        "categories": cats_out,
    }
```

- [ ] **Step 6: Обновить backend/app/api/router.py**

```python
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.venues import router as venues_router
from app.api.dishes import router as dishes_router
from app.api.menu import router as menu_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(venues_router)
api_router.include_router(dishes_router)
api_router.include_router(menu_router)
```

- [ ] **Step 7: Запустить тесты**

```bash
pytest tests/test_dishes.py -v
```

Ожидаем: 4 теста PASSED.

- [ ] **Step 8: Запустить все тесты**

```bash
pytest -v --tb=short
```

Ожидаем: все PASSED.

- [ ] **Step 9: Commit**

```bash
git add backend/
git commit -m "feat: Categories + Dishes CRUD, public menu endpoint /menu/{slug}"
```

---

## Task 7: Парсер меню (BeautifulSoup4 + static HTML)

**Files:**
- Create: `backend/app/workers/parser.py`
- Create: `backend/app/api/parse_jobs.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_parser.py`

- [ ] **Step 1: Написать тест на парсер**

```python
# tests/test_parser.py
import pytest
from unittest.mock import patch, MagicMock
from app.workers.parser import extract_dishes_from_html


SAMPLE_HTML = """
<html>
<body>
  <div class="menu-section">
    <h2>Напитки</h2>
    <div class="dish">
      <span class="dish-name">Капучино</span>
      <span class="dish-price">220 руб</span>
      <span class="dish-weight">300 мл</span>
    </div>
    <div class="dish">
      <span class="dish-name">Латте</span>
      <span class="dish-price">250 руб</span>
    </div>
  </div>
  <div class="menu-section">
    <h2>Еда</h2>
    <div class="dish">
      <span class="dish-name">Сэндвич</span>
      <span class="dish-price">180 руб</span>
      <span class="dish-weight">200 г</span>
    </div>
  </div>
</body>
</html>
"""


def test_extract_dishes_returns_list():
    dishes = extract_dishes_from_html(SAMPLE_HTML)
    assert isinstance(dishes, list)
    assert len(dishes) >= 1


def test_extract_dishes_has_required_fields():
    dishes = extract_dishes_from_html(SAMPLE_HTML)
    for dish in dishes:
        assert "name" in dish
        assert "price" in dish
        assert dish["name"]


def test_extract_price_parsed_as_float():
    dishes = extract_dishes_from_html(SAMPLE_HTML)
    for dish in dishes:
        if dish["price"] is not None:
            assert isinstance(dish["price"], float)
```

- [ ] **Step 2: Запустить — убедиться FAIL**

```bash
pytest tests/test_parser.py -v
```

- [ ] **Step 3: Создать backend/app/workers/parser.py**

```python
import re
import requests
from bs4 import BeautifulSoup


def fetch_html(url: str, timeout: int = 30) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MenuScan/1.0)"}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def _parse_price(text: str) -> float | None:
    match = re.search(r"[\d\s]+[,.]?\d*", text.replace("\xa0", " "))
    if not match:
        return None
    cleaned = match.group().replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_dishes_from_html(html: str) -> list[dict]:
    """
    Эвристический парсер: ищет повторяющиеся блоки с названием и ценой.
    Возвращает список dicts: {name, price, weight, category}.
    """
    soup = BeautifulSoup(html, "html.parser")
    dishes = []
    current_category = None

    # Стратегия 1: ищем секции с заголовком + блоки блюд
    price_pattern = re.compile(r"\d[\d\s]*[,.]?\d*\s*(руб|₽|rub|р\.?)", re.IGNORECASE)

    # Находим все элементы, содержащие цену
    price_elements = soup.find_all(string=price_pattern)

    seen_names = set()
    for price_el in price_elements:
        price_text = price_el.strip()
        price = _parse_price(price_text)
        if price is None or price <= 0 or price > 100000:
            continue

        # Поднимаемся к родительскому блоку блюда
        parent = price_el.parent
        for _ in range(4):
            if parent is None:
                break
            block_text = parent.get_text(separator=" ", strip=True)
            # Ищем название: первый текстовый кусок без цифр достаточной длины
            name_candidates = [
                t.strip() for t in parent.stripped_strings
                if not re.search(r"\d", t) and len(t.strip()) > 2
            ]
            if name_candidates:
                name = name_candidates[0]
                if name not in seen_names:
                    seen_names.add(name)
                    # Ищем граммовку
                    weight_match = re.search(r"\d+\s*(г|мл|гр|ml|g)\b", block_text, re.IGNORECASE)
                    weight = weight_match.group() if weight_match else None
                    # Ищем категорию — ближайший заголовок выше
                    heading = parent.find_previous(["h1", "h2", "h3", "h4"])
                    category = heading.get_text(strip=True) if heading else None
                    dishes.append({
                        "name": name,
                        "price": price,
                        "weight": weight,
                        "category": category,
                        "description": None,
                    })
                break
            parent = parent.parent

    return dishes


async def parse_venue_menu(venue_id: str, source_url: str, db) -> int:
    """
    Парсит меню по URL, сохраняет блюда в БД.
    Возвращает количество найденных блюд.
    """
    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.parse_job import ParseJob
    from app.models.dish import Dish
    from app.models.category import Category
    import uuid
    from datetime import datetime, timezone

    html = fetch_html(source_url)
    raw_dishes = extract_dishes_from_html(html)

    # Создаём/обновляем категории
    category_map: dict[str, uuid.UUID] = {}
    for d in raw_dishes:
        cat_name = d.get("category") or "Основное"
        if cat_name not in category_map:
            slug = re.sub(r"[^a-zа-я0-9]+", "-", cat_name.lower()).strip("-") or "cat"
            existing = await db.execute(
                select(Category).where(
                    Category.venue_id == uuid.UUID(venue_id),
                    Category.name == cat_name,
                )
            )
            cat = existing.scalar_one_or_none()
            if not cat:
                cat = Category(
                    venue_id=uuid.UUID(venue_id),
                    name=cat_name,
                    slug=f"{slug}-{len(category_map)}",
                )
                db.add(cat)
                await db.flush()
            category_map[cat_name] = cat.id

    # Сохраняем блюда
    for d in raw_dishes:
        cat_name = d.get("category") or "Основное"
        cat_id = category_map.get(cat_name)
        dish = Dish(
            venue_id=uuid.UUID(venue_id),
            category_id=cat_id,
            name=d["name"],
            price=d["price"],
            weight=d.get("weight"),
            description=d.get("description"),
        )
        db.add(dish)

    await db.commit()
    return len(raw_dishes)
```

- [ ] **Step 4: Создать backend/app/api/parse_jobs.py**

```python
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.parse_job import ParseJob
from app.models.venue import Venue
from app.services.venue import get_venue_or_404
from app.workers.parser import parse_venue_menu

router = APIRouter(tags=["parse"])


async def _run_parse_job(job_id: uuid.UUID, venue_id: str, source_url: str):
    from app.core.deps import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        job = await db.get(ParseJob, job_id)
        if not job:
            return
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()
        try:
            count = await parse_venue_menu(venue_id, source_url, db)
            job.status = "done"
            job.dishes_found = count
            job.finished_at = datetime.now(timezone.utc)
            # Обновляем venue status
            venue = await db.get(Venue, uuid.UUID(venue_id))
            if venue:
                venue.parse_status = "done"
            await db.commit()
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.finished_at = datetime.now(timezone.utc)
            venue = await db.get(Venue, uuid.UUID(venue_id))
            if venue:
                venue.parse_status = "failed"
            await db.commit()


@router.post("/venues/{venue_id}/reparse", status_code=202)
async def reparse_venue(
    venue_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    venue = await get_venue_or_404(db, venue_id, current_user.id)
    if not venue.website_url:
        raise HTTPException(400, "Venue has no website_url to parse")

    job = ParseJob(venue_id=venue_id, source_url=venue.website_url, status="queued")
    db.add(job)
    venue.parse_status = "parsing"
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(_run_parse_job, job.id, str(venue_id), venue.website_url)
    return {"parse_job_id": str(job.id), "status": "queued"}


@router.get("/venues/{venue_id}/parse-status")
async def parse_status(
    venue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, current_user.id)
    result = await db.execute(
        select(ParseJob).where(ParseJob.venue_id == venue_id).order_by(ParseJob.started_at.desc().nullslast())
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(404, "No parse job found")
    return {
        "job_id": str(job.id),
        "status": job.status,
        "dishes_found": job.dishes_found,
        "finished_at": job.finished_at,
        "error_message": job.error_message,
    }
```

- [ ] **Step 5: Обновить backend/app/api/router.py**

```python
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.venues import router as venues_router
from app.api.dishes import router as dishes_router
from app.api.menu import router as menu_router
from app.api.parse_jobs import router as parse_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(venues_router)
api_router.include_router(dishes_router)
api_router.include_router(menu_router)
api_router.include_router(parse_router)
```

- [ ] **Step 6: Запустить тесты парсера**

```bash
pytest tests/test_parser.py -v
```

Ожидаем: 3 теста PASSED.

- [ ] **Step 7: Запустить все тесты**

```bash
pytest -v --tb=short
```

Ожидаем: все PASSED.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: menu parser — BeautifulSoup4 heuristic scraper + parse job API"
```

---

## Task 8: QR Generator + PDF + S3

**Files:**
- Create: `backend/app/services/qr.py`
- Create: `backend/app/api/qr.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_qr.py`

- [ ] **Step 1: Написать тест на QR генерацию**

```python
# tests/test_qr.py
import pytest
from app.services.qr import generate_qr_png_bytes, build_qr_pdf


def test_generate_qr_png_bytes_returns_bytes():
    data = generate_qr_png_bytes("https://menuscan.io/menu/cafe/table/1")
    assert isinstance(data, bytes)
    assert len(data) > 0
    # PNG magic bytes
    assert data[:4] == b"\x89PNG"


def test_build_qr_pdf_returns_bytes():
    tables = [
        {"number": 1, "label": "Стол 1", "url": "https://menuscan.io/menu/cafe/table/1"},
        {"number": 2, "label": "Стол 2", "url": "https://menuscan.io/menu/cafe/table/2"},
    ]
    pdf_bytes = build_qr_pdf(venue_name="Тест Кафе", tables=tables)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100
    # PDF magic bytes
    assert pdf_bytes[:4] == b"%PDF"
```

- [ ] **Step 2: Запустить — убедиться FAIL**

```bash
pytest tests/test_qr.py -v
```

- [ ] **Step 3: Создать backend/app/services/qr.py**

```python
import io
import qrcode
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def generate_qr_png_bytes(url: str, box_size: int = 10, border: int = 2) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def build_qr_pdf(venue_name: str, tables: list[dict]) -> bytes:
    """
    Генерирует PDF формата A4, 4 QR-кода на лист.
    tables: [{number, label, url}, ...]
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_width, page_height = A4

    cols, rows = 2, 2
    margin = 1.5 * cm
    cell_w = (page_width - 2 * margin) / cols
    cell_h = (page_height - 2 * margin) / rows
    qr_size = min(cell_w, cell_h) * 0.65

    for i, table in enumerate(tables):
        if i > 0 and i % (cols * rows) == 0:
            c.showPage()

        pos = i % (cols * rows)
        col = pos % cols
        row = pos // cols

        x = margin + col * cell_w + (cell_w - qr_size) / 2
        y = page_height - margin - (row + 1) * cell_h + (cell_h - qr_size) / 2

        qr_bytes = generate_qr_png_bytes(table["url"])
        qr_reader = ImageReader(io.BytesIO(qr_bytes))
        c.drawImage(qr_reader, x, y, width=qr_size, height=qr_size)

        label = table.get("label") or f"Стол {table['number']}"
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x + qr_size / 2, y - 0.5 * cm, label)
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + qr_size / 2, y - 0.9 * cm, venue_name)

    c.save()
    buf.seek(0)
    return buf.read()


def upload_pdf_to_s3(pdf_bytes: bytes, key: str) -> str:
    import boto3
    from app.core.config import settings

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    # Создаём бакет если нет
    try:
        s3.head_bucket(Bucket=settings.S3_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=settings.S3_BUCKET)

    s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )
    return f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{key}"
```

- [ ] **Step 4: Создать backend/app/api/qr.py**

```python
import uuid
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.table import Table
from app.models.qr_batch import QrBatch
from app.services.venue import get_venue_or_404
from app.services.qr import build_qr_pdf, upload_pdf_to_s3
from app.core.config import settings

router = APIRouter(tags=["qr"])


async def _generate_and_upload(venue_id: uuid.UUID, batch_id: uuid.UUID, venue_name: str, slug: str):
    from app.core.deps import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Table).where(Table.venue_id == venue_id, Table.is_active == True).order_by(Table.number)
        )
        tables = result.scalars().all()

        table_data = [
            {
                "number": t.number,
                "label": t.label or f"Стол {t.number}",
                "url": f"{settings.MENU_BASE_URL}/{slug}/table/{t.id}",
            }
            for t in tables
        ]

        pdf_bytes = build_qr_pdf(venue_name=venue_name, tables=table_data)
        key = f"qr/{venue_id}/{batch_id}.pdf"
        url = upload_pdf_to_s3(pdf_bytes, key)

        batch = await db.get(QrBatch, batch_id)
        if batch:
            batch.pdf_url = url
            await db.commit()


@router.post("/venues/{venue_id}/qr/generate", status_code=202)
async def generate_qr(
    venue_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    venue = await get_venue_or_404(db, venue_id, current_user.id)
    batch = QrBatch(venue_id=venue_id, table_count=venue.table_count)
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    background_tasks.add_task(_generate_and_upload, venue_id, batch.id, venue.name, venue.slug)
    return {"batch_id": str(batch.id), "status": "generating"}


@router.get("/venues/{venue_id}/qr/download")
async def download_qr(
    venue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_venue_or_404(db, venue_id, current_user.id)
    result = await db.execute(
        select(QrBatch).where(QrBatch.venue_id == venue_id, QrBatch.pdf_url.isnot(None))
        .order_by(QrBatch.generated_at.desc())
    )
    batch = result.scalars().first()
    if not batch or not batch.pdf_url:
        raise HTTPException(404, "QR PDF not generated yet")
    return RedirectResponse(url=batch.pdf_url)
```

- [ ] **Step 5: Обновить backend/app/api/router.py**

```python
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.venues import router as venues_router
from app.api.dishes import router as dishes_router
from app.api.menu import router as menu_router
from app.api.parse_jobs import router as parse_router
from app.api.qr import router as qr_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(venues_router)
api_router.include_router(dishes_router)
api_router.include_router(menu_router)
api_router.include_router(parse_router)
api_router.include_router(qr_router)
```

- [ ] **Step 6: Запустить тесты QR**

```bash
pytest tests/test_qr.py -v
```

Ожидаем: 2 теста PASSED.

- [ ] **Step 7: Запустить все тесты**

```bash
pytest -v --tb=short --cov=app --cov-report=term-missing
```

Ожидаем: все PASSED, coverage > 70%.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: QR PNG + PDF generator, S3 upload, /qr/generate and /qr/download endpoints"
```

---

## Task 9: GitHub Actions CI/CD

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Создать .github/workflows/ci.yml**

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: menuscan
          POSTGRES_PASSWORD: menuscan
          POSTGRES_DB: menuscan_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          cd backend
          pip install -e ".[dev]"

      - name: Run migrations
        env:
          DATABASE_URL: postgresql+asyncpg://menuscan:menuscan@localhost:5432/menuscan_test
          TEST_DATABASE_URL: postgresql+asyncpg://menuscan:menuscan@localhost:5432/menuscan_test
          SECRET_KEY: test-secret-key-for-ci
        run: |
          cd backend
          alembic upgrade head

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://menuscan:menuscan@localhost:5432/menuscan_test
          TEST_DATABASE_URL: postgresql+asyncpg://menuscan:menuscan@localhost:5432/menuscan_test
          SECRET_KEY: test-secret-key-for-ci
          REDIS_URL: redis://localhost:6379/0
          S3_ENDPOINT_URL: http://localhost:9000
          S3_ACCESS_KEY: minioadmin
          S3_SECRET_KEY: minioadmin
          S3_BUCKET: menuscan
          MENU_BASE_URL: http://localhost:3001
        run: |
          cd backend
          pytest -v --tb=short --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: backend/coverage.xml
          fail_ci_if_error: false
```

- [ ] **Step 2: Создать .gitignore если нет**

```
# .gitignore
__pycache__/
*.pyc
.env
.venv/
venv/
*.egg-info/
.pytest_cache/
.coverage
coverage.xml
dist/
.DS_Store
node_modules/
.next/
```

- [ ] **Step 3: Финальный прогон всех тестов локально**

```bash
cd backend
pytest -v --tb=short --cov=app --cov-report=term-missing
```

Ожидаем: все тесты PASSED, coverage > 70%.

- [ ] **Step 4: Commit и push**

```bash
git add .github/ .gitignore
git commit -m "ci: GitHub Actions — lint + test + coverage on push"
git push origin main
```

- [ ] **Step 5: Убедиться что CI зелёный**

Открыть https://github.com/Sergqmts/QR_for_menuscan/actions и дождаться зелёного чека.

---

## Self-Review

### Spec coverage (из docs/01_PRD.md и docs/06_ROADMAP.md)

| Требование из Фазы 1 | Задача |
|---|---|
| Docker Compose: FastAPI + PostgreSQL + Redis | Task 1 |
| Alembic: первичная схема БД | Task 2 |
| CI/CD: GitHub Actions (lint + tests) | Task 9 |
| POST /auth/register, POST /auth/login, JWT | Task 3, 4 |
| CRUD /venues — создание, список, обновление | Task 5 |
| CRUD /tables — автогенерация при создании venue | Task 5 |
| CRUD /categories + CRUD /dishes | Task 6 |
| Parser Worker: BeautifulSoup4 | Task 7 |
| GET /venues/{id}/parse-status | Task 7 |
| Fallback CSV import | ❌ Не включён в MVP план (добавить в Task 7 при необходимости) |
| Генерация QR через qrcode | Task 8 |
| Сборка PDF ReportLab (4 QR на лист) | Task 8 |
| Загрузка PDF в S3 | Task 8 |
| GET /venues/{id}/qr/download | Task 8 |

**Пропущено:** CSV-импорт блюд (fallback). Добавляется отдельным эндпоинтом `POST /venues/{id}/dishes/import-csv` в рамках Task 7 при желании.

### Placeholder scan
Найдено: нет "TBD", "TODO", "implement later".

### Type consistency
- `VenueOut.model_validate(venue)` — используется в venues.py, parse_jobs.py — ок.
- `DishOut.model_validate(d)` — dishes.py и menu.py — ок.
- `TableOut.model_validate(t)` — venues.py — ок.
- `get_venue_or_404(db, venue_id, owner_id)` — сигнатура согласована во всех вызовах.
