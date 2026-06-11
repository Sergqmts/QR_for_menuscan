# MenuScan Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working backend with infrastructure, Auth API, static HTML menu parser, and QR PDF generation — so an owner can register, paste a URL, and download a PDF with QR codes.

**Architecture:** FastAPI async backend with PostgreSQL (via asyncpg/SQLAlchemy) and Redis, running in Docker Compose locally. Parser runs as an asyncio background task. QR PDF is uploaded to MinIO (local S3-compatible storage).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (async), asyncpg, Alembic, aioredis, BeautifulSoup4, httpx, qrcode, ReportLab, Pillow, boto3, pytest-asyncio, hatchling

---

## File Map

```
backend/
├── app/
│   ├── main.py                      # FastAPI app factory, router includes
│   ├── api/
│   │   ├── deps.py                  # get_db(), get_current_user()
│   │   ├── auth.py                  # POST /auth/register, /login
│   │   ├── venues.py                # CRUD /venues
│   │   ├── tables.py                # GET/PATCH /venues/{id}/tables
│   │   ├── categories.py            # CRUD /venues/{id}/categories
│   │   ├── dishes.py                # CRUD /venues/{id}/dishes
│   │   ├── menu.py                  # GET /menu/{slug} (public)
│   │   ├── parse.py                 # GET parse-status, POST reparse
│   │   └── qr.py                    # POST generate, GET download
│   ├── core/
│   │   ├── config.py                # Settings via pydantic-settings
│   │   ├── security.py              # JWT, bcrypt helpers
│   │   └── database.py              # async engine + session factory
│   ├── models/
│   │   ├── base.py                  # DeclarativeBase
│   │   ├── __init__.py              # import all models
│   │   ├── user.py
│   │   ├── venue.py
│   │   ├── table.py
│   │   ├── category.py
│   │   ├── dish.py
│   │   ├── parse_job.py
│   │   └── qr_batch.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── venue.py
│   │   ├── table.py
│   │   ├── category.py
│   │   ├── dish.py
│   │   └── menu.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── venue_service.py
│   │   ├── menu_service.py
│   │   └── qr_service.py
│   └── workers/
│       ├── __init__.py
│       └── parser.py                # BeautifulSoup4 scraper + CSV import
├── alembic/
│   ├── versions/
│   │   └── 0001_initial_schema.py
│   ├── env.py
│   └── alembic.ini
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_venues.py
│   ├── test_categories.py
│   ├── test_dishes.py
│   ├── test_menu.py
│   ├── test_parser.py
│   └── test_qr.py
├── Dockerfile
├── pyproject.toml
└── .env.example

docker-compose.yml
.github/workflows/ci.yml
README.md
```

---

## Task 1: Repo Skeleton + Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/database.py`
- Create: `backend/Dockerfile`
- Create: `README.md`

- [ ] **Step 1: Create root docker-compose.yml**

```yaml
version: "3.9"

services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: ./backend/.env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: menuscan
      POSTGRES_PASSWORD: menuscan
      POSTGRES_DB: menuscan
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
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
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

volumes:
  pg_data:
  minio_data:
```

- [ ] **Step 2: Create backend/pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "menuscan-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.29.0",
    "alembic>=1.13.1",
    "pydantic-settings>=2.2.1",
    "pydantic[email]>=2.7.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "redis[hiredis]>=5.0.4",
    "boto3>=1.34.0",
    "beautifulsoup4>=4.12.3",
    "httpx>=0.27.0",
    "qrcode[pil]>=7.4.2",
    "reportlab>=4.2.0",
    "pillow>=10.3.0",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.7",
    "pytest-cov>=5.0.0",
    "anyio>=4.3.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 3: Create backend/.env.example**

```bash
DATABASE_URL=postgresql+asyncpg://menuscan:menuscan@db:5432/menuscan
REDIS_URL=redis://redis:6379/0
SECRET_KEY=change-me-in-production-use-openssl-rand-hex-32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=menuscan
S3_PUBLIC_URL=http://localhost:9000/menuscan

ENVIRONMENT=development
```

Copy to `backend/.env` (add `.env` to `.gitignore`).

- [ ] **Step 4: Create backend/app/core/config.py**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket_name: str
    s3_public_url: str

    environment: str = "development"


settings = Settings()
```

- [ ] **Step 5: Create backend/app/core/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 6: Create backend/app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MenuScan API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Create backend/Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install -e ".[dev]"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 8: Create empty __init__.py files**

Create `backend/app/__init__.py`, `backend/app/core/__init__.py`, `backend/app/api/__init__.py`, `backend/app/models/__init__.py`, `backend/app/schemas/__init__.py`, `backend/app/services/__init__.py`, `backend/app/workers/__init__.py` — all empty.

- [ ] **Step 9: Start services and verify health endpoint**

```bash
cp backend/.env.example backend/.env
docker compose up -d
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 10: Commit**

```bash
git add docker-compose.yml backend/
git commit -m "feat: project skeleton — Docker Compose, FastAPI app, config"
```

---

## Task 2: SQLAlchemy Models + Alembic Initial Migration

**Files:**
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/venue.py`
- Create: `backend/app/models/table.py`
- Create: `backend/app/models/category.py`
- Create: `backend/app/models/dish.py`
- Create: `backend/app/models/parse_job.py`
- Create: `backend/app/models/qr_batch.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic.ini`

- [ ] **Step 1: Create backend/app/models/base.py**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: Create backend/app/models/user.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 3: Create backend/app/models/venue.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: Create backend/app/models/table.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Table(Base):
    __tablename__ = "tables"
    __table_args__ = (UniqueConstraint("venue_id", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    qr_code_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: Create backend/app/models/category.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, ForeignKey, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("venue_id", "slug"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 6: Create backend/app/models/dish.py**

```python
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, DateTime, Numeric, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Dish(Base):
    __tablename__ = "dishes"
    __table_args__ = (
        Index("idx_dishes_venue_id", "venue_id"),
        Index("idx_dishes_category_id", "category_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 7: Create backend/app/models/parse_job.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ParseJob(Base):
    __tablename__ = "parse_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    dishes_found: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 8: Create backend/app/models/qr_batch.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import Integer, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class QRBatch(Base):
    __tablename__ = "qr_batches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    table_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 9: Create backend/app/models/__init__.py**

```python
from app.models.user import User
from app.models.venue import Venue
from app.models.table import Table
from app.models.category import Category
from app.models.dish import Dish
from app.models.parse_job import ParseJob
from app.models.qr_batch import QRBatch

__all__ = ["User", "Venue", "Table", "Category", "Dish", "ParseJob", "QRBatch"]
```

- [ ] **Step 10: Initialize Alembic and configure env.py**

```bash
cd backend
alembic init alembic
```

Replace the generated `backend/alembic/env.py` with:

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.core.config import settings
import app.models  # noqa: import all models via __init__
from app.models.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
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

- [ ] **Step 11: Generate and apply initial migration**

```bash
cd backend
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

Verify tables exist:

```bash
docker compose exec db psql -U menuscan -c "\dt"
```

Expected: `users`, `venues`, `tables`, `categories`, `dishes`, `parse_jobs`, `qr_batches` all listed.

- [ ] **Step 12: Commit**

```bash
git add backend/app/models/ backend/alembic/ backend/alembic.ini
git commit -m "feat: SQLAlchemy models + Alembic initial migration"
```

---

## Task 3: Auth API — Register, Login, JWT

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/app/services/auth_service.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/conftest.py`:

```python
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.core.database import get_db
from app.models.base import Base

TEST_DATABASE_URL = "postgresql+asyncpg://menuscan:menuscan@localhost:5432/menuscan_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def db_session():
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

Create `backend/tests/test_auth.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post("/auth/register", json={
        "email": "owner@test.ru",
        "password": "SecurePass123",
        "full_name": "Тест Тестов"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["email"] == "owner@test.ru"
    assert "access_token" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@test.ru", "password": "Pass123", "full_name": "A"}
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/auth/register", json={
        "email": "login@test.ru", "password": "Pass123", "full_name": "B"
    })
    response = await client.post("/auth/login", json={
        "email": "login@test.ru", "password": "Pass123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "email": "wrongpass@test.ru", "password": "Correct123", "full_name": "C"
    })
    response = await client.post("/auth/login", json={
        "email": "wrongpass@test.ru", "password": "Wrong123"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client):
    reg = await client.post("/auth/register", json={
        "email": "me@test.ru", "password": "Pass123", "full_name": "D"
    })
    token = reg.json()["access_token"]
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@test.ru"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && pytest tests/test_auth.py -v
```

Expected: FAIL — routes not defined yet (404 or ImportError)

- [ ] **Step 3: Create backend/app/core/security.py**

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
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": subject, "exp": expire}, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except JWTError:
        return None
```

- [ ] **Step 4: Create backend/app/schemas/auth.py**

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

- [ ] **Step 5: Create backend/app/services/auth_service.py**

```python
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token
from app.schemas.auth import RegisterRequest


async def register_user(db: AsyncSession, data: RegisterRequest) -> tuple[User, str]:
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        id=uuid.uuid4(),
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


async def login_user(db: AsyncSession, email: str, password: str) -> str:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return create_access_token(str(user.id))
```

- [ ] **Step 6: Create backend/app/api/deps.py**

```python
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer()


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

- [ ] **Step 7: Create backend/app/api/auth.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, RegisterResponse, TokenResponse, UserOut
from app.services.auth_service import register_user, login_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user, token = await register_user(db, data)
    return RegisterResponse(user=UserOut.model_validate(user), access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    token = await login_user(db, data.email, data.password)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
```

- [ ] **Step 8: Update backend/app/main.py to include auth router**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router

app = FastAPI(title="MenuScan API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 9: Create test database and run tests**

```bash
docker compose exec db psql -U menuscan -c "CREATE DATABASE menuscan_test;"
cd backend && pytest tests/test_auth.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 10: Commit**

```bash
git add backend/app/core/security.py backend/app/schemas/auth.py backend/app/api/ backend/app/services/auth_service.py backend/tests/
git commit -m "feat: auth API — register, login, JWT bearer middleware"
```

---

## Task 4: Venues CRUD + Auto-create Tables

**Files:**
- Create: `backend/app/schemas/venue.py`
- Create: `backend/app/schemas/table.py`
- Create: `backend/app/services/venue_service.py`
- Create: `backend/app/api/venues.py`
- Create: `backend/app/api/tables.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_venues.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_venues.py`:

```python
import pytest, uuid as uuid_mod


async def _register_and_token(client) -> str:
    email = f"v_{uuid_mod.uuid4().hex[:6]}@test.ru"
    r = await client.post("/auth/register", json={"email": email, "password": "Pass123", "full_name": "O"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_create_venue(client):
    token = await _register_and_token(client)
    r = await client.post("/venues", json={
        "name": "Кафе Тест", "table_count": 5, "address": "Москва"
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 202
    data = r.json()
    assert data["venue"]["name"] == "Кафе Тест"
    assert data["venue"]["slug"] == "kafe-test"


@pytest.mark.asyncio
async def test_list_venues(client):
    token = await _register_and_token(client)
    await client.post("/venues", json={"name": "Зал 1", "table_count": 2},
                      headers={"Authorization": f"Bearer {token}"})
    r = await client.get("/venues", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()["venues"]) >= 1


@pytest.mark.asyncio
async def test_get_venue(client):
    token = await _register_and_token(client)
    cr = await client.post("/venues", json={"name": "Детальное", "table_count": 2},
                            headers={"Authorization": f"Bearer {token}"})
    venue_id = cr.json()["venue"]["id"]
    r = await client.get(f"/venues/{venue_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["id"] == venue_id


@pytest.mark.asyncio
async def test_patch_venue(client):
    token = await _register_and_token(client)
    cr = await client.post("/venues", json={"name": "Старое", "table_count": 1},
                            headers={"Authorization": f"Bearer {token}"})
    venue_id = cr.json()["venue"]["id"]
    r = await client.patch(f"/venues/{venue_id}", json={"name": "Новое"},
                            headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["name"] == "Новое"


@pytest.mark.asyncio
async def test_tables_auto_created(client):
    token = await _register_and_token(client)
    cr = await client.post("/venues", json={"name": "Со Столами", "table_count": 4},
                            headers={"Authorization": f"Bearer {token}"})
    venue_id = cr.json()["venue"]["id"]
    r = await client.get(f"/venues/{venue_id}/tables", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()["tables"]) == 4
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && pytest tests/test_venues.py -v
```

Expected: All FAIL (404 Not Found)

- [ ] **Step 3: Create backend/app/schemas/venue.py**

```python
from pydantic import BaseModel
import uuid
from datetime import datetime


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
    address: str | None
    cuisine_type: str | None
    table_count: int
    parse_status: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VenueCreateResponse(BaseModel):
    venue: VenueOut
    parse_job_id: uuid.UUID | None = None
```

- [ ] **Step 4: Create backend/app/schemas/table.py**

```python
from pydantic import BaseModel
import uuid
from datetime import datetime


class TableOut(BaseModel):
    id: uuid.UUID
    number: int
    label: str | None
    qr_code_url: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TableUpdate(BaseModel):
    label: str | None = None
    is_active: bool | None = None
```

- [ ] **Step 5: Create backend/app/services/venue_service.py**

```python
import uuid
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.venue import Venue
from app.models.table import Table
from app.schemas.venue import VenueCreate, VenueUpdate


def _slugify(name: str) -> str:
    table = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"zh",
        "з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o",
        "п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"kh","ц":"ts",
        "ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"
    }
    slug = name.lower()
    slug = re.sub(r"[а-яё]", lambda m: table.get(m.group(), ""), slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "venue"


async def create_venue(db: AsyncSession, owner_id: uuid.UUID, data: VenueCreate) -> tuple[Venue, uuid.UUID | None]:
    base_slug = _slugify(data.name)
    slug = base_slug
    counter = 1
    while True:
        existing = await db.execute(select(Venue).where(Venue.slug == slug))
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    venue = Venue(
        id=uuid.uuid4(),
        owner_id=owner_id,
        name=data.name,
        slug=slug,
        website_url=data.website_url,
        address=data.address,
        cuisine_type=data.cuisine_type,
        table_count=data.table_count,
        parse_status="pending" if not data.website_url else "parsing",
    )
    db.add(venue)
    await db.flush()

    for n in range(1, data.table_count + 1):
        db.add(Table(id=uuid.uuid4(), venue_id=venue.id, number=n, label=f"Стол {n}"))

    job_id = None
    if data.website_url:
        from app.models.parse_job import ParseJob
        job = ParseJob(id=uuid.uuid4(), venue_id=venue.id, source_url=data.website_url, status="queued")
        db.add(job)
        job_id = job.id

    await db.commit()
    await db.refresh(venue)

    if job_id:
        import asyncio
        from app.workers.parser import run_parse_job
        from app.core.database import AsyncSessionLocal
        async def _run():
            async with AsyncSessionLocal() as bg_db:
                await run_parse_job(bg_db, job_id)
        asyncio.create_task(_run())

    return venue, job_id


async def get_venue_or_404(db: AsyncSession, venue_id: uuid.UUID, owner_id: uuid.UUID) -> Venue:
    result = await db.execute(select(Venue).where(Venue.id == venue_id, Venue.owner_id == owner_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")
    return venue


async def update_venue(db: AsyncSession, venue: Venue, data: VenueUpdate) -> Venue:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(venue, field, value)
    await db.commit()
    await db.refresh(venue)
    return venue
```

- [ ] **Step 6: Create backend/app/api/venues.py**

```python
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.venue import Venue
from app.schemas.venue import VenueCreate, VenueUpdate, VenueOut, VenueCreateResponse
from app.services.venue_service import create_venue, get_venue_or_404, update_venue

router = APIRouter(prefix="/venues", tags=["venues"])


@router.post("", response_model=VenueCreateResponse, status_code=202)
async def create(data: VenueCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    venue, job_id = await create_venue(db, user.id, data)
    return VenueCreateResponse(venue=VenueOut.model_validate(venue), parse_job_id=job_id)


@router.get("", response_model=dict)
async def list_venues(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Venue).where(Venue.owner_id == user.id))
    return {"venues": [VenueOut.model_validate(v) for v in result.scalars().all()]}


@router.get("/{venue_id}", response_model=VenueOut)
async def get_venue(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return VenueOut.model_validate(await get_venue_or_404(db, venue_id, user.id))


@router.patch("/{venue_id}", response_model=VenueOut)
async def patch_venue(venue_id: uuid.UUID, data: VenueUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    venue = await get_venue_or_404(db, venue_id, user.id)
    return VenueOut.model_validate(await update_venue(db, venue, data))
```

- [ ] **Step 7: Create backend/app/api/tables.py**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.table import Table
from app.schemas.table import TableOut, TableUpdate
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["tables"])


@router.get("/{venue_id}/tables", response_model=dict)
async def list_tables(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Table).where(Table.venue_id == venue_id).order_by(Table.number))
    return {"tables": [TableOut.model_validate(t) for t in result.scalars().all()]}


@router.patch("/{venue_id}/tables/{table_id}", response_model=TableOut)
async def patch_table(venue_id: uuid.UUID, table_id: uuid.UUID, data: TableUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Table).where(Table.id == table_id, Table.venue_id == venue_id))
    table = result.scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(table, field, value)
    await db.commit()
    await db.refresh(table)
    return TableOut.model_validate(table)
```

- [ ] **Step 8: Update backend/app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.venues import router as venues_router
from app.api.tables import router as tables_router

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


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 9: Run tests**

```bash
cd backend && pytest tests/test_venues.py -v
```

Expected: All 5 PASS

- [ ] **Step 10: Commit**

```bash
git add backend/app/schemas/venue.py backend/app/schemas/table.py backend/app/services/venue_service.py backend/app/api/venues.py backend/app/api/tables.py backend/app/main.py backend/tests/test_venues.py
git commit -m "feat: venues CRUD + auto-create tables on venue creation"
```

---

## Task 5: Categories + Dishes CRUD

**Files:**
- Create: `backend/app/schemas/category.py`
- Create: `backend/app/schemas/dish.py`
- Create: `backend/app/api/categories.py`
- Create: `backend/app/api/dishes.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_categories.py`
- Create: `backend/tests/test_dishes.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_categories.py`:

```python
import pytest, uuid as uuid_mod


async def _setup(client):
    email = f"c_{uuid_mod.uuid4().hex[:6]}@test.ru"
    r = await client.post("/auth/register", json={"email": email, "password": "Pass123", "full_name": "O"})
    token = r.json()["access_token"]
    vr = await client.post("/venues", json={"name": f"V{uuid_mod.uuid4().hex[:4]}", "table_count": 1},
                            headers={"Authorization": f"Bearer {token}"})
    return token, vr.json()["venue"]["id"]


@pytest.mark.asyncio
async def test_create_category(client):
    token, venue_id = await _setup(client)
    r = await client.post(f"/venues/{venue_id}/categories",
                          json={"name": "Завтраки", "slug": "breakfast"},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    assert r.json()["name"] == "Завтраки"


@pytest.mark.asyncio
async def test_list_categories(client):
    token, venue_id = await _setup(client)
    await client.post(f"/venues/{venue_id}/categories", json={"name": "Супы", "slug": "soups"},
                      headers={"Authorization": f"Bearer {token}"})
    r = await client.get(f"/venues/{venue_id}/categories", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()["categories"]) >= 1
```

Create `backend/tests/test_dishes.py`:

```python
import pytest, uuid as uuid_mod


async def _setup(client):
    email = f"d_{uuid_mod.uuid4().hex[:6]}@test.ru"
    r = await client.post("/auth/register", json={"email": email, "password": "Pass123", "full_name": "O"})
    token = r.json()["access_token"]
    vr = await client.post("/venues", json={"name": f"V{uuid_mod.uuid4().hex[:4]}", "table_count": 1},
                            headers={"Authorization": f"Bearer {token}"})
    venue_id = vr.json()["venue"]["id"]
    cr = await client.post(f"/venues/{venue_id}/categories", json={"name": "Горячее", "slug": "hot"},
                            headers={"Authorization": f"Bearer {token}"})
    return token, venue_id, cr.json()["id"]


@pytest.mark.asyncio
async def test_create_dish(client):
    token, venue_id, cat_id = await _setup(client)
    r = await client.post(f"/venues/{venue_id}/dishes", json={
        "category_id": cat_id, "name": "Борщ", "price": 350.00, "weight": "300мл"
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    assert r.json()["name"] == "Борщ"


@pytest.mark.asyncio
async def test_update_dish_price(client):
    token, venue_id, cat_id = await _setup(client)
    cr = await client.post(f"/venues/{venue_id}/dishes", json={
        "category_id": cat_id, "name": "Солянка", "price": 400.00
    }, headers={"Authorization": f"Bearer {token}"})
    dish_id = cr.json()["id"]
    r = await client.patch(f"/venues/{venue_id}/dishes/{dish_id}", json={"price": 450.00},
                            headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert float(r.json()["price"]) == 450.00


@pytest.mark.asyncio
async def test_delete_dish(client):
    token, venue_id, cat_id = await _setup(client)
    cr = await client.post(f"/venues/{venue_id}/dishes", json={
        "category_id": cat_id, "name": "Удаляемое", "price": 100.00
    }, headers={"Authorization": f"Bearer {token}"})
    dish_id = cr.json()["id"]
    r = await client.delete(f"/venues/{venue_id}/dishes/{dish_id}",
                             headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && pytest tests/test_categories.py tests/test_dishes.py -v
```

- [ ] **Step 3: Create backend/app/schemas/category.py**

```python
from pydantic import BaseModel
import uuid
from datetime import datetime


class CategoryCreate(BaseModel):
    name: str
    slug: str
    sort_order: int = 0
    is_visible: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    is_visible: bool | None = None


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    sort_order: int
    is_visible: bool
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create backend/app/schemas/dish.py**

```python
from pydantic import BaseModel
from decimal import Decimal
import uuid
from datetime import datetime


class DishCreate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str
    description: str | None = None
    price: Decimal
    weight: str | None = None
    calories: str | None = None
    tags: list[str] = []
    allergens: list[str] = []
    is_available: bool = True
    sort_order: int = 0


class DishUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = None
    description: str | None = None
    price: Decimal | None = None
    weight: str | None = None
    calories: str | None = None
    tags: list[str] | None = None
    allergens: list[str] | None = None
    is_available: bool | None = None
    sort_order: int | None = None


class DishOut(BaseModel):
    id: uuid.UUID
    venue_id: uuid.UUID
    category_id: uuid.UUID | None
    name: str
    description: str | None
    price: Decimal
    weight: str | None
    calories: str | None
    image_url: str | None
    tags: list
    allergens: list
    is_available: bool
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Create backend/app/api/categories.py**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryOut
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["categories"])


@router.post("/{venue_id}/categories", response_model=CategoryOut, status_code=201)
async def create_category(venue_id: uuid.UUID, data: CategoryCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    cat = Category(id=uuid.uuid4(), venue_id=venue_id, **data.model_dump())
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return CategoryOut.model_validate(cat)


@router.get("/{venue_id}/categories", response_model=dict)
async def list_categories(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Category).where(Category.venue_id == venue_id).order_by(Category.sort_order))
    return {"categories": [CategoryOut.model_validate(c) for c in result.scalars().all()]}


@router.patch("/{venue_id}/categories/{cat_id}", response_model=CategoryOut)
async def patch_category(venue_id: uuid.UUID, cat_id: uuid.UUID, data: CategoryUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Category).where(Category.id == cat_id, Category.venue_id == venue_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(cat, field, value)
    await db.commit()
    await db.refresh(cat)
    return CategoryOut.model_validate(cat)


@router.delete("/{venue_id}/categories/{cat_id}", status_code=204)
async def delete_category(venue_id: uuid.UUID, cat_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Category).where(Category.id == cat_id, Category.venue_id == venue_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    await db.delete(cat)
    await db.commit()
```

- [ ] **Step 6: Create backend/app/api/dishes.py**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dish import Dish
from app.schemas.dish import DishCreate, DishUpdate, DishOut
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["dishes"])


@router.post("/{venue_id}/dishes", response_model=DishOut, status_code=201)
async def create_dish(venue_id: uuid.UUID, data: DishCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    dish = Dish(id=uuid.uuid4(), venue_id=venue_id, **data.model_dump())
    db.add(dish)
    await db.commit()
    await db.refresh(dish)
    return DishOut.model_validate(dish)


@router.get("/{venue_id}/dishes", response_model=dict)
async def list_dishes(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Dish).where(Dish.venue_id == venue_id).order_by(Dish.sort_order))
    return {"dishes": [DishOut.model_validate(d) for d in result.scalars().all()]}


@router.patch("/{venue_id}/dishes/{dish_id}", response_model=DishOut)
async def patch_dish(venue_id: uuid.UUID, dish_id: uuid.UUID, data: DishUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Dish).where(Dish.id == dish_id, Dish.venue_id == venue_id))
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(dish, field, value)
    await db.commit()
    await db.refresh(dish)
    return DishOut.model_validate(dish)


@router.delete("/{venue_id}/dishes/{dish_id}", status_code=204)
async def delete_dish(venue_id: uuid.UUID, dish_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(select(Dish).where(Dish.id == dish_id, Dish.venue_id == venue_id))
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    await db.delete(dish)
    await db.commit()
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


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Run tests**

```bash
cd backend && pytest tests/test_categories.py tests/test_dishes.py -v
```

Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/ backend/app/api/categories.py backend/app/api/dishes.py backend/app/main.py backend/tests/
git commit -m "feat: categories and dishes CRUD endpoints"
```

---

## Task 6: Public Menu Endpoint

**Files:**
- Create: `backend/app/schemas/menu.py`
- Create: `backend/app/services/menu_service.py`
- Create: `backend/app/api/menu.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_menu.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_menu.py`:

```python
import pytest, uuid as uuid_mod


async def _create_venue_with_dishes(client):
    email = f"m_{uuid_mod.uuid4().hex[:6]}@test.ru"
    r = await client.post("/auth/register", json={"email": email, "password": "Pass123", "full_name": "O"})
    token = r.json()["access_token"]
    vr = await client.post("/venues", json={"name": "Меню Кафе", "table_count": 2},
                            headers={"Authorization": f"Bearer {token}"})
    venue = vr.json()["venue"]
    cr = await client.post(f"/venues/{venue['id']}/categories", json={"name": "Горячее", "slug": "hot"},
                            headers={"Authorization": f"Bearer {token}"})
    cat_id = cr.json()["id"]
    await client.post(f"/venues/{venue['id']}/dishes", json={
        "category_id": cat_id, "name": "Борщ", "price": 350.00
    }, headers={"Authorization": f"Bearer {token}"})
    return venue["slug"]


@pytest.mark.asyncio
async def test_public_menu(client):
    slug = await _create_venue_with_dishes(client)
    r = await client.get(f"/menu/{slug}")
    assert r.status_code == 200
    data = r.json()
    assert data["venue"]["name"] == "Меню Кафе"
    assert len(data["categories"]) == 1
    assert data["categories"][0]["dishes"][0]["name"] == "Борщ"


@pytest.mark.asyncio
async def test_menu_not_found(client):
    r = await client.get("/menu/nonexistent-venue-xyz123")
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && pytest tests/test_menu.py -v
```

- [ ] **Step 3: Create backend/app/schemas/menu.py**

```python
from pydantic import BaseModel
from decimal import Decimal
import uuid


class PublicDishOut(BaseModel):
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

    model_config = {"from_attributes": True}


class PublicCategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    sort_order: int
    dishes: list[PublicDishOut]


class PublicVenueOut(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    settings: dict


class PublicMenuOut(BaseModel):
    venue: PublicVenueOut
    categories: list[PublicCategoryOut]
```

- [ ] **Step 4: Create backend/app/services/menu_service.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models.venue import Venue
from app.models.category import Category
from app.models.dish import Dish
from app.schemas.menu import PublicMenuOut, PublicVenueOut, PublicCategoryOut, PublicDishOut


async def get_public_menu(db: AsyncSession, venue_slug: str) -> PublicMenuOut:
    result = await db.execute(select(Venue).where(Venue.slug == venue_slug, Venue.is_active == True))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    cats_result = await db.execute(
        select(Category).where(Category.venue_id == venue.id, Category.is_visible == True)
        .order_by(Category.sort_order)
    )
    categories = cats_result.scalars().all()

    dishes_result = await db.execute(
        select(Dish).where(Dish.venue_id == venue.id, Dish.is_available == True).order_by(Dish.sort_order)
    )
    dishes_by_cat: dict = {}
    for dish in dishes_result.scalars().all():
        dishes_by_cat.setdefault(str(dish.category_id), []).append(dish)

    return PublicMenuOut(
        venue=PublicVenueOut(id=venue.id, name=venue.name, logo_url=venue.logo_url, settings=venue.settings),
        categories=[
            PublicCategoryOut(
                id=cat.id, name=cat.name, slug=cat.slug, sort_order=cat.sort_order,
                dishes=[PublicDishOut.model_validate(d) for d in dishes_by_cat.get(str(cat.id), [])]
            )
            for cat in categories
        ],
    )
```

- [ ] **Step 5: Create backend/app/api/menu.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.menu import PublicMenuOut
from app.services.menu_service import get_public_menu

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("/{venue_slug}", response_model=PublicMenuOut)
async def get_menu(venue_slug: str, db: AsyncSession = Depends(get_db)):
    return await get_public_menu(db, venue_slug)
```

- [ ] **Step 6: Update backend/app/main.py** — add menu router after dishes_router:

```python
from app.api.menu import router as menu_router
# add after other includes:
app.include_router(menu_router)
```

Full updated `main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.venues import router as venues_router
from app.api.tables import router as tables_router
from app.api.categories import router as categories_router
from app.api.dishes import router as dishes_router
from app.api.menu import router as menu_router

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


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Run tests**

```bash
cd backend && pytest tests/test_menu.py -v
```

Expected: Both PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/menu.py backend/app/services/menu_service.py backend/app/api/menu.py backend/app/main.py backend/tests/test_menu.py
git commit -m "feat: public menu endpoint GET /menu/{slug}"
```

---

## Task 7: Menu Parser (BeautifulSoup4 + CSV fallback)

**Files:**
- Create: `backend/app/workers/__init__.py`
- Create: `backend/app/workers/parser.py`
- Create: `backend/app/api/parse.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_parser.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_parser.py`:

```python
import pytest
from app.workers.parser import normalize_price, extract_dishes_from_html, parse_csv_content


def test_normalize_price_integer():
    assert normalize_price("350") == 350.0


def test_normalize_price_with_rub():
    assert normalize_price("350 руб") == 350.0


def test_normalize_price_with_spaces():
    assert normalize_price("1 200 руб.") == 1200.0


def test_normalize_price_decimal():
    assert normalize_price("299,90") == 299.9


def test_normalize_price_invalid():
    assert normalize_price("бесплатно") is None


def test_extract_dishes_from_html_basic():
    html = """
    <html><body>
    <div class="menu-item">
        <span class="name">Борщ</span>
        <span class="price">350 руб</span>
        <span class="weight">300мл</span>
    </div>
    <div class="menu-item">
        <span class="name">Котлета</span>
        <span class="price">420 руб</span>
    </div>
    </body></html>
    """
    dishes = extract_dishes_from_html(html, selectors={
        "item": ".menu-item",
        "name": ".name",
        "price": ".price",
        "weight": ".weight",
    })
    assert len(dishes) == 2
    assert dishes[0]["name"] == "Борщ"
    assert dishes[0]["price"] == 350.0
    assert dishes[0]["weight"] == "300мл"
    assert dishes[1]["name"] == "Котлета"
    assert dishes[1]["price"] == 420.0


def test_extract_dishes_empty_html():
    dishes = extract_dishes_from_html("<html></html>", selectors={
        "item": ".menu-item", "name": ".name", "price": ".price"
    })
    assert dishes == []


def test_parse_csv():
    csv_content = "name,price,weight,category\nБорщ,350,300мл,Супы\nКотлета,420,,Горячее"
    dishes = parse_csv_content(csv_content)
    assert len(dishes) == 2
    assert dishes[0] == {"name": "Борщ", "price": 350.0, "weight": "300мл", "category": "Супы"}
    assert dishes[1] == {"name": "Котлета", "price": 420.0, "weight": None, "category": "Горячее"}
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && pytest tests/test_parser.py -v
```

Expected: `ImportError` — module doesn't exist yet

- [ ] **Step 3: Create backend/app/workers/__init__.py** (empty file)

- [ ] **Step 4: Create backend/app/workers/parser.py**

```python
import re
import csv
import io
import uuid
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


def normalize_price(raw: str) -> float | None:
    if not raw:
        return None
    cleaned = raw.replace("\xa0", " ").replace(" ", "")
    cleaned = re.sub(r"[рублRUBруб\.₽]", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_dishes_from_html(html: str, selectors: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(selectors.get("item", ".menu-item"))
    results = []
    for item in items:
        name_el = item.select_one(selectors.get("name", ".name"))
        price_el = item.select_one(selectors.get("price", ".price"))
        weight_el = item.select_one(selectors.get("weight", ".weight"))
        desc_el = item.select_one(selectors.get("description", ".description"))

        name = name_el.get_text(strip=True) if name_el else None
        price_raw = price_el.get_text(strip=True) if price_el else None
        price = normalize_price(price_raw) if price_raw else None

        if not name or price is None:
            continue

        results.append({
            "name": name,
            "price": price,
            "weight": weight_el.get_text(strip=True) if weight_el else None,
            "description": desc_el.get_text(strip=True) if desc_el else None,
            "category": None,
        })
    return results


def parse_csv_content(csv_content: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_content))
    results = []
    for row in reader:
        name = row.get("name", "").strip()
        price = normalize_price(row.get("price", ""))
        if not name or price is None:
            continue
        weight = row.get("weight", "").strip() or None
        category = row.get("category", "").strip() or None
        results.append({"name": name, "price": price, "weight": weight, "category": category})
    return results


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

- [ ] **Step 5: Run parser tests — expect PASS**

```bash
cd backend && pytest tests/test_parser.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 6: Create backend/app/api/parse.py**

```python
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException
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
        "error_message": job.error_message,
        "finished_at": job.finished_at,
    }


@router.post("/{venue_id}/reparse", status_code=202)
async def reparse(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.venue import Venue
    venue = await get_venue_or_404(db, venue_id, user.id)
    if not venue.website_url:
        raise HTTPException(status_code=400, detail="No website URL set")

    job = ParseJob(id=uuid.uuid4(), venue_id=venue_id, source_url=venue.website_url, status="queued")
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
```

- [ ] **Step 7: Update backend/app/main.py** — add parse router:

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


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Run all tests**

```bash
cd backend && pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/workers/ backend/app/api/parse.py backend/app/main.py backend/tests/test_parser.py
git commit -m "feat: BeautifulSoup4 menu parser + CSV fallback + parse-status endpoint"
```

---

## Task 8: QR Code Generator + PDF + MinIO Upload

**Files:**
- Create: `backend/app/services/qr_service.py`
- Create: `backend/app/api/qr.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_qr.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_qr.py`:

```python
import pytest
from app.services.qr_service import generate_qr_image_bytes, build_qr_pdf


def test_generate_qr_image_bytes():
    data = generate_qr_image_bytes("https://menu.menuscan.io/test/table/1")
    assert isinstance(data, bytes)
    assert data[:4] == b'\x89PNG'


def test_build_qr_pdf_small():
    entries = [{"table_number": i, "url": f"https://menu.menuscan.io/cafe/table/{i}"} for i in range(1, 5)]
    pdf = build_qr_pdf(venue_name="Тест Кафе", qr_entries=entries)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b'%PDF'


def test_build_qr_pdf_12_tables():
    entries = [{"table_number": i, "url": f"https://menu.menuscan.io/cafe/table/{i}"} for i in range(1, 13)]
    pdf = build_qr_pdf(venue_name="Большое Кафе", qr_entries=entries)
    assert pdf[:4] == b'%PDF'
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && pytest tests/test_qr.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create backend/app/services/qr_service.py**

```python
import io
import boto3
from botocore.config import Config
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image

from app.core.config import settings


def generate_qr_image_bytes(url: str) -> bytes:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_qr_pdf(venue_name: str, qr_entries: list[dict]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_width, page_height = A4
    cols, rows = 2, 2
    per_page = cols * rows
    qr_size = 7 * cm
    cell_w = page_width / cols
    cell_h = (page_height - 3 * cm) / rows

    for page_start in range(0, max(len(qr_entries), 1), per_page):
        page_entries = qr_entries[page_start:page_start + per_page]
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_width / 2, page_height - 1.5 * cm, venue_name)

        for idx, entry in enumerate(page_entries):
            col = idx % cols
            row = idx // cols
            x = col * cell_w + (cell_w - qr_size) / 2
            y = page_height - 3 * cm - (row + 1) * cell_h + (cell_h - qr_size) / 2
            qr_img = Image.open(io.BytesIO(generate_qr_image_bytes(entry["url"])))
            c.drawImage(ImageReader(qr_img), x, y, width=qr_size, height=qr_size)
            c.setFont("Helvetica-Bold", 12)
            c.drawCentredString(col * cell_w + cell_w / 2, y - 0.6 * cm, f"Стол {entry['table_number']}")

        c.showPage()

    c.save()
    return buf.getvalue()


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket_exists() -> None:
    s3 = _get_s3_client()
    try:
        s3.head_bucket(Bucket=settings.s3_bucket_name)
    except Exception:
        s3.create_bucket(Bucket=settings.s3_bucket_name)
        s3.put_bucket_policy(
            Bucket=settings.s3_bucket_name,
            Policy=(
                '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*",'
                '"Action":"s3:GetObject","Resource":"arn:aws:s3:::' + settings.s3_bucket_name + '/*"}]}'
            )
        )


def upload_pdf_to_s3(pdf_bytes: bytes, key: str) -> str:
    ensure_bucket_exists()
    _get_s3_client().put_object(
        Bucket=settings.s3_bucket_name, Key=key, Body=pdf_bytes, ContentType="application/pdf"
    )
    return f"{settings.s3_public_url}/{key}"
```

- [ ] **Step 4: Run QR tests — expect PASS**

```bash
cd backend && pytest tests/test_qr.py -v
```

Expected: All 3 PASS

- [ ] **Step 5: Create backend/app/api/qr.py**

```python
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.table import Table
from app.models.qr_batch import QRBatch
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["qr"])


@router.post("/{venue_id}/qr/generate", status_code=202)
async def generate_qr(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    venue = await get_venue_or_404(db, venue_id, user.id)
    tables_result = await db.execute(
        select(Table).where(Table.venue_id == venue_id, Table.is_active == True).order_by(Table.number)
    )
    tables = tables_result.scalars().all()

    batch = QRBatch(id=uuid.uuid4(), venue_id=venue_id, table_count=len(tables))
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    batch_id = batch.id
    venue_name = venue.name
    venue_slug = venue.slug
    table_data = [(t.id, t.number) for t in tables]

    from app.core.database import AsyncSessionLocal

    async def _generate():
        from app.services.qr_service import build_qr_pdf, upload_pdf_to_s3
        qr_entries = [
            {"table_number": num, "url": f"https://menu.menuscan.io/{venue_slug}/table/{num}"}
            for _, num in table_data
        ]
        pdf_bytes = build_qr_pdf(venue_name=venue_name, qr_entries=qr_entries)
        key = f"qr/{venue_id}/{batch_id}.pdf"
        pdf_url = upload_pdf_to_s3(pdf_bytes, key)

        async with AsyncSessionLocal() as bg_db:
            result = await bg_db.execute(select(QRBatch).where(QRBatch.id == batch_id))
            b = result.scalar_one()
            b.pdf_url = pdf_url
            for tid, tnum in table_data:
                tr = await bg_db.execute(select(Table).where(Table.id == tid))
                t = tr.scalar_one()
                t.qr_code_url = f"https://menu.menuscan.io/{venue_slug}/table/{tnum}"
            await bg_db.commit()

    asyncio.create_task(_generate())
    return {"batch_id": batch_id, "status": "generating"}


@router.get("/{venue_id}/qr/download")
async def download_qr(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(
        select(QRBatch)
        .where(QRBatch.venue_id == venue_id, QRBatch.pdf_url.isnot(None))
        .order_by(QRBatch.generated_at.desc())
        .limit(1)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="No QR PDF generated yet")
    return RedirectResponse(url=batch.pdf_url)
```

- [ ] **Step 6: Update backend/app/main.py** — final version with all routers:

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


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Run full test suite**

```bash
cd backend && pytest tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/qr_service.py backend/app/api/qr.py backend/app/main.py backend/tests/test_qr.py
git commit -m "feat: QR code + PDF generation with MinIO/S3 upload"
```

---

## Task 9: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `README.md`

- [ ] **Step 1: Create .github/workflows/ci.yml**

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
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        working-directory: backend
        run: pip install -e ".[dev]"
      - name: Run tests
        working-directory: backend
        env:
          DATABASE_URL: postgresql+asyncpg://menuscan:menuscan@localhost:5432/menuscan_test
          REDIS_URL: redis://localhost:6379/0
          SECRET_KEY: ci-secret-key
          ALGORITHM: HS256
          ACCESS_TOKEN_EXPIRE_MINUTES: 60
          S3_ENDPOINT_URL: http://localhost:9000
          S3_ACCESS_KEY: minioadmin
          S3_SECRET_KEY: minioadmin
          S3_BUCKET_NAME: menuscan-ci
          S3_PUBLIC_URL: http://localhost:9000/menuscan-ci
          ENVIRONMENT: test
        run: pytest tests/ -v --cov=app --cov-report=term-missing

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check backend/app/
```

- [ ] **Step 2: Create README.md**

```markdown
# MenuScan

SaaS QR-меню с совместной корзиной стола для кафе и ресторанов.

## Быстрый старт

```bash
cp backend/.env.example backend/.env
docker compose up -d
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs  
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin)

## Тесты

```bash
cd backend
pytest tests/ -v
```

## Миграции

```bash
cd backend
alembic upgrade head
```
```

- [ ] **Step 3: Run full test suite with coverage**

```bash
cd backend && pytest tests/ -v --cov=app --cov-report=term-missing
```

Expected: All tests PASS, coverage ≥ 60% on `app/api/`, `app/services/`, `app/workers/`

- [ ] **Step 4: Commit**

```bash
git add .github/ README.md
git commit -m "feat: GitHub Actions CI — lint + pytest on push"
```

---

## Phase 1 Exit Criteria

- [ ] `docker compose up -d` → all 4 services healthy (api, db, redis, minio)
- [ ] `POST /auth/register` → 201 with JWT
- [ ] `POST /auth/login` → 200 with JWT
- [ ] `POST /venues` with `table_count=5` → 202, tables auto-created
- [ ] `GET /menu/{slug}` (no auth) → 200 with categories + dishes
- [ ] `GET /venues/{id}/parse-status` → returns job status
- [ ] `POST /venues/{id}/qr/generate` → 202, async PDF creation starts
- [ ] `GET /venues/{id}/qr/download` → 302 redirect to MinIO PDF
- [ ] `pytest tests/ -v` → all tests PASS
- [ ] CI pipeline passes on push to main

---

*When Phase 1 is complete: an owner can register, create a venue, watch parse progress, and download a printable PDF of QR codes for every table.*
