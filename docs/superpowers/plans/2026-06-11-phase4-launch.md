# Phase 4 — Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Playwright JS-parser, wire up ARQ job queue, build production Docker Compose, configure Railway + Render deployments, and define beta/launch criteria.

**Architecture:** A separate `parser-worker` container runs an ARQ worker that polls Redis for parse jobs and executes them — using httpx first, auto-falling back to Playwright when fewer than 3 dishes are found. The API enqueues jobs via a lazy ARQ pool instead of `asyncio.create_task`. Two deployment configs (`railway.toml`, `render.yaml`) plus `docker-compose.prod.yml` cover all target environments.

**Tech Stack:** ARQ 0.25+, Playwright 1.44+, Docker Compose, Railway, Render, UptimeRobot

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `backend/app/core/arq_queue.py` | Lazy ARQ pool singleton used by API to enqueue jobs |
| Create | `backend/app/workers/arq_worker.py` | ARQ WorkerSettings + `run_parse_job` task entrypoint |
| Create | `backend/app/workers/playwright_parser.py` | `fetch_html_auto` (httpx → Playwright fallback) + `MENU_SELECTORS` |
| Create | `backend/Dockerfile.worker` | Docker image with Chromium for the parser-worker service |
| Create | `docker-compose.prod.yml` | Production Compose (no `--reload`, adds `parser-worker`, no MinIO) |
| Create | `railway.toml` | Railway deployment config for API service |
| Create | `render.yaml` | Render deployment config for API + worker + databases |
| Create | `backend/tests/test_playwright_parser.py` | Unit tests for auto-detect logic (mocked Playwright) |
| Modify | `backend/pyproject.toml` | Add `arq>=0.25.0` to main deps; add `[worker]` extras with `playwright` |
| Modify | `backend/app/api/parse.py` | Replace `asyncio.create_task` with `arq_pool.enqueue_job` |
| Modify | `backend/app/workers/parser.py` | Replace inline httpx+selectors block with `fetch_html_auto` call |
| Modify | `backend/app/main.py` | Upgrade `/health` to check DB + Redis connectivity |

---

## Task 1: Add ARQ to dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add `arq` to main dependencies and add `[worker]` extras**

In `backend/pyproject.toml`, update the `dependencies` list and add an optional group:

```toml
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
    "arq>=0.25.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.7",
    "pytest-cov>=5.0.0",
    "anyio>=4.3.0",
]
worker = [
    "playwright>=1.44.0",
]
```

- [ ] **Step 2: Install updated deps**

```bash
cd backend && pip install -e ".[dev]"
```

Expected: `Successfully installed arq-...`

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "feat: add arq dependency, worker extras with playwright"
```

---

## Task 2: ARQ queue client (API side)

**Files:**
- Create: `backend/app/core/arq_queue.py`

- [ ] **Step 1: Create `arq_queue.py`**

```python
from urllib.parse import urlparse

from arq import create_pool
from arq.connections import RedisSettings

_pool = None


def _redis_settings() -> RedisSettings:
    from app.core.config import settings
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int((parsed.path or "/0").lstrip("/") or 0),
    )


async def get_arq_pool():
    global _pool
    if _pool is None:
        _pool = await create_pool(_redis_settings())
    return _pool
```

- [ ] **Step 2: Verify import works**

```bash
cd backend && python -c "from app.core.arq_queue import get_arq_pool; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/arq_queue.py
git commit -m "feat: add arq queue pool client"
```

---

## Task 3: Playwright fetcher + tests

**Files:**
- Create: `backend/app/workers/playwright_parser.py`
- Create: `backend/tests/test_playwright_parser.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_playwright_parser.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_playwright_fetch_returns_page_html():
    """_playwright_fetch returns the page HTML after 3 scrolls."""
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html>menu</html>")
    mock_page.goto = AsyncMock()
    mock_page.evaluate = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser.close = AsyncMock()

    mock_chromium = AsyncMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_pw_ctx = MagicMock()
    mock_pw_ctx.chromium = mock_chromium
    mock_pw_ctx.__aenter__ = AsyncMock(return_value=mock_pw_ctx)
    mock_pw_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workers.playwright_parser.async_playwright", return_value=mock_pw_ctx):
        from app.workers.playwright_parser import _playwright_fetch
        result = await _playwright_fetch("http://example.com")

    assert result == "<html>menu</html>"
    mock_page.goto.assert_awaited_once_with(
        "http://example.com", wait_until="networkidle", timeout=60000
    )
    assert mock_page.evaluate.await_count == 3


@pytest.mark.asyncio
async def test_fetch_html_auto_skips_playwright_when_enough_dishes():
    """fetch_html_auto returns httpx HTML directly when ≥3 dishes found."""
    rich_html = """<html><body>
    <div class="menu-item"><span class="name">Борщ</span><span class="price">100</span></div>
    <div class="menu-item"><span class="name">Щи</span><span class="price">90</span></div>
    <div class="menu-item"><span class="name">Котлета</span><span class="price">200</span></div>
    </body></html>"""

    mock_response = MagicMock()
    mock_response.text = rich_html
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.workers.playwright_parser.httpx.AsyncClient", return_value=mock_client), \
         patch("app.workers.playwright_parser._playwright_fetch", new_callable=AsyncMock) as mock_pw:
        from importlib import reload
        import app.workers.playwright_parser as mod
        reload(mod)
        result = await mod.fetch_html_auto("http://example.com")

    assert result == rich_html
    mock_pw.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_html_auto_uses_playwright_when_sparse():
    """fetch_html_auto calls _playwright_fetch when httpx yields <3 dishes."""
    sparse_html = "<html><body></body></html>"
    playwright_html = "<html><body>full menu content</body></html>"

    mock_response = MagicMock()
    mock_response.text = sparse_html
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.workers.playwright_parser.httpx.AsyncClient", return_value=mock_client), \
         patch("app.workers.playwright_parser._playwright_fetch", new_callable=AsyncMock, return_value=playwright_html) as mock_pw:
        from importlib import reload
        import app.workers.playwright_parser as mod
        reload(mod)
        result = await mod.fetch_html_auto("http://example.com")

    assert result == playwright_html
    mock_pw.assert_awaited_once_with("http://example.com")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_playwright_parser.py -v
```

Expected: `ImportError: cannot import name '_playwright_fetch' from 'app.workers.playwright_parser'`

- [ ] **Step 3: Create `playwright_parser.py`**

```python
import httpx
from playwright.async_api import async_playwright

MENU_SELECTORS = {
    "item": ".menu-item, .dish, .product, [class*='menu-item'], [class*='dish']",
    "name": ".name, .title, h3, h4, [class*='name'], [class*='title']",
    "price": ".price, [class*='price'], [class*='cost']",
    "weight": ".weight, .volume, [class*='weight'], [class*='gram']",
    "description": ".description, .desc, [class*='desc']",
}


async def _playwright_fetch(url: str, timeout_ms: int = 60000) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(1000)
        html = await page.content()
        await browser.close()
        return html


async def fetch_html_auto(url: str) -> str:
    """Fetch page HTML; falls back to Playwright when httpx yields <3 dishes."""
    from app.workers.parser import extract_dishes_from_html

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    if len(extract_dishes_from_html(resp.text, MENU_SELECTORS)) < 3:
        return await _playwright_fetch(url)
    return resp.text
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_playwright_parser.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/playwright_parser.py backend/tests/test_playwright_parser.py
git commit -m "feat: playwright parser with httpx auto-detect fallback"
```

---

## Task 4: Update parser.py to use fetch_html_auto

**Files:**
- Modify: `backend/app/workers/parser.py` (lines 127–138, the httpx block inside `run_parse_job`)

- [ ] **Step 1: Replace the httpx fetch block and inline selectors in `run_parse_job`**

In `backend/app/workers/parser.py`, replace this block inside `run_parse_job`:

```python
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
```

With:

```python
    try:
        from app.workers.playwright_parser import fetch_html_auto, MENU_SELECTORS
        html = await fetch_html_auto(job.source_url)
        dishes_data = extract_dishes_from_html(html, MENU_SELECTORS)
```

Also remove the `import httpx` at the top of `parser.py` since it's no longer used directly.

- [ ] **Step 2: Run existing parser tests**

```bash
cd backend && pytest tests/test_parser.py -v
```

Expected: `5 passed` (same tests as before — they test pure functions that didn't change)

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/parser.py
git commit -m "refactor: parser uses fetch_html_auto with playwright fallback"
```

---

## Task 5: ARQ worker entrypoint

**Files:**
- Create: `backend/app/workers/arq_worker.py`

- [ ] **Step 1: Create `arq_worker.py`**

```python
import uuid

from arq.connections import RedisSettings
from urllib.parse import urlparse


async def run_parse_job(ctx: dict, job_id: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.workers.parser import run_parse_job as execute_parse_job

    async with AsyncSessionLocal() as db:
        await execute_parse_job(db, uuid.UUID(job_id))


def _redis_settings() -> RedisSettings:
    from app.core.config import settings
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int((parsed.path or "/0").lstrip("/") or 0),
    )


class WorkerSettings:
    functions = [run_parse_job]
    redis_settings = _redis_settings()
    max_jobs = 5
    job_timeout = 120
    max_tries = 3
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from app.workers.arq_worker import WorkerSettings; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/arq_worker.py
git commit -m "feat: arq worker entrypoint for parse jobs"
```

---

## Task 6: Update parse.py API to use ARQ enqueue

**Files:**
- Modify: `backend/app/api/parse.py`

- [ ] **Step 1: Replace both `asyncio.create_task` calls**

Replace the full `reparse` and `reparse_diff` endpoints. The new versions drop the `asyncio` import and the inner `_run` closure, and use `arq_pool.enqueue_job` instead:

```python
import uuid
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
    venue = await get_venue_or_404(db, venue_id, user.id)
    if not venue.website_url:
        raise HTTPException(status_code=400, detail="No website URL set")

    job = ParseJob(id=uuid.uuid4(), venue_id=venue_id, source_url=venue.website_url, status="queued", diff_mode=False)
    db.add(job)
    venue.parse_status = "parsing"
    await db.commit()
    await db.refresh(job)

    from app.core.arq_queue import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("run_parse_job", str(job.id))
    return {"parse_job_id": job.id, "status": "queued"}


@router.post("/{venue_id}/reparse-diff", status_code=202)
async def reparse_diff(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    venue = await get_venue_or_404(db, venue_id, user.id)
    if not venue.website_url:
        raise HTTPException(status_code=400, detail="No website URL set")

    job = ParseJob(id=uuid.uuid4(), venue_id=venue_id, source_url=venue.website_url, status="queued", diff_mode=True)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    from app.core.arq_queue import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("run_parse_job", str(job.id))
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

- [ ] **Step 2: Run full test suite**

```bash
cd backend && pytest -v
```

Expected: all previously passing tests still pass.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/parse.py
git commit -m "feat: parse endpoints enqueue jobs via arq instead of asyncio.create_task"
```

---

## Task 7: Upgrade /health endpoint

**Files:**
- Modify: `backend/app/main.py` (line 62–64, the `/health` handler)

- [ ] **Step 1: Replace the basic health endpoint**

Replace:

```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```

With:

```python
@app.get("/health")
async def health():
    from sqlalchemy import text
    from redis.asyncio import from_url as redis_from_url
    from app.core.config import settings

    db_ok = False
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    redis_ok = False
    try:
        r = redis_from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        pass

    status = "ok" if (db_ok and redis_ok) else "degraded"
    return {"status": status, "db": db_ok, "redis": redis_ok}
```

- [ ] **Step 2: Start the API and verify the endpoint**

```bash
cd backend && uvicorn app.main:app --port 8000 &
sleep 2
curl http://localhost:8000/health
kill %1
```

Expected (when DB+Redis are running via docker-compose):
```json
{"status":"ok","db":true,"redis":true}
```

Expected (when DB+Redis are NOT running):
```json
{"status":"degraded","db":false,"redis":false}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: /health checks db and redis connectivity"
```

---

## Task 8: Dockerfile.worker

**Files:**
- Create: `backend/Dockerfile.worker`

- [ ] **Step 1: Create `Dockerfile.worker`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install -e ".[worker]"
RUN playwright install chromium --with-deps

COPY . .

CMD ["python", "-m", "arq", "app.workers.arq_worker.WorkerSettings"]
```

- [ ] **Step 2: Build the image to verify it compiles**

```bash
cd backend && docker build -f Dockerfile.worker -t menuscan-worker:test .
```

Expected: `Successfully built ...` (takes 3–5 min first time due to Chromium download)

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile.worker
git commit -m "feat: dockerfile for playwright parser worker"
```

---

## Task 9: docker-compose.prod.yml

**Files:**
- Create: `docker-compose.prod.yml` (repo root)

- [ ] **Step 1: Create `docker-compose.prod.yml`**

```yaml
version: "3.9"

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "127.0.0.1:8000:8000"
    env_file: ./backend/.env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  parser-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    env_file: ./backend/.env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      api:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: menuscan
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: menuscan
    volumes:
      - pg_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U menuscan"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pg_data:
  redis_data:
```

Note: No MinIO service — production uses external S3/Cloudflare R2 (`S3_ENDPOINT_URL` set in `.env`). No port forwarding for DB/Redis — only API is exposed on `127.0.0.1:8000` (behind a reverse proxy like Caddy or Nginx).

- [ ] **Step 2: Validate the compose file syntax**

```bash
docker compose -f docker-compose.prod.yml config --quiet
```

Expected: exits 0 with no output.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat: production docker-compose with parser-worker, no minio"
```

---

## Task 10: Railway deployment config

**Files:**
- Create: `railway.toml` (repo root)

Railway deploys each service separately. You'll create two Railway services in the dashboard: one for `api`, one for `parser-worker`. Both point to this repo; the `railway.toml` covers the API service. The worker service is configured via Railway dashboard (see Step 2).

- [ ] **Step 1: Create `railway.toml`**

```toml
[build]
builder = "dockerfile"
dockerfilePath = "backend/Dockerfile"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 5
```

- [ ] **Step 2: Document Railway setup (add to `docs/superpowers/plans/2026-06-11-phase4-launch.md` comments)**

Railway setup steps (run manually in Railway dashboard):
1. Create project → Add service → GitHub repo → select `main` branch
2. Service 1 (API): root service, uses `railway.toml` automatically
3. Service 2 (Parser Worker): Add service → same repo → set **Root Directory** to `backend`, **Dockerfile path** to `Dockerfile.worker`, **Start command** to `python -m arq app.workers.arq_worker.WorkerSettings`
4. Add managed **PostgreSQL** plugin → copy `DATABASE_URL` → set as env var `DATABASE_URL` on both services
5. Add managed **Redis** plugin → copy `REDIS_URL` → set as `REDIS_URL` on both services
6. Set remaining env vars on both services: `SECRET_KEY`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_NAME`, `S3_PUBLIC_URL`, `ALGORITHM=HS256`, `ENVIRONMENT=production`

- [ ] **Step 3: Commit**

```bash
git add railway.toml
git commit -m "feat: railway deployment config"
```

---

## Task 11: Render deployment config

**Files:**
- Create: `render.yaml` (repo root)

- [ ] **Step 1: Create `render.yaml`**

```yaml
services:
  - type: web
    name: menuscan-api
    env: docker
    dockerfilePath: ./backend/Dockerfile
    dockerContext: ./backend
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: menuscan-pg
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: menuscan-redis
          type: redis
          property: connectionString
      - key: SECRET_KEY
        sync: false
      - key: S3_ENDPOINT_URL
        sync: false
      - key: S3_ACCESS_KEY
        sync: false
      - key: S3_SECRET_KEY
        sync: false
      - key: S3_BUCKET_NAME
        sync: false
      - key: S3_PUBLIC_URL
        sync: false
      - key: ALGORITHM
        value: HS256
      - key: ENVIRONMENT
        value: production

  - type: worker
    name: menuscan-parser
    env: docker
    dockerfilePath: ./backend/Dockerfile.worker
    dockerContext: ./backend
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: menuscan-pg
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: menuscan-redis
          type: redis
          property: connectionString
      - key: SECRET_KEY
        sync: false
      - key: S3_ENDPOINT_URL
        sync: false
      - key: S3_ACCESS_KEY
        sync: false
      - key: S3_SECRET_KEY
        sync: false
      - key: S3_BUCKET_NAME
        sync: false
      - key: S3_PUBLIC_URL
        sync: false
      - key: ALGORITHM
        value: HS256
      - key: ENVIRONMENT
        value: production

  - type: redis
    name: menuscan-redis
    plan: starter
    maxmemoryPolicy: allkeys-lru

databases:
  - name: menuscan-pg
    plan: starter
    databaseName: menuscan
    user: menuscan
```

- [ ] **Step 2: Validate YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('render.yaml'))" && echo "valid"
```

Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add render.yaml
git commit -m "feat: render deployment config with api, worker, pg, redis"
```

---

## Task 12: Beta readiness check + UptimeRobot setup

This task is operational, not code. No new files.

- [ ] **Step 1: Run alembic migrations against production DB after first deploy**

```bash
# SSH into Railway/Render shell or run via one-off command
cd backend && alembic upgrade head
```

Expected: `Running upgrade ... -> ...` for each pending migration.

- [ ] **Step 2: Smoke-test the deployed API**

```bash
# Replace YOUR_DOMAIN with Railway/Render URL
curl https://YOUR_DOMAIN/health
```

Expected:
```json
{"status":"ok","db":true,"redis":true}
```

- [ ] **Step 3: Set up UptimeRobot monitor**

1. Go to [uptimerobot.com](https://uptimerobot.com) → Add New Monitor
2. Type: **HTTP(s)**
3. Friendly Name: `MenuScan API`
4. URL: `https://YOUR_DOMAIN/health`
5. Monitoring Interval: **5 minutes**
6. Alert contacts: add email `sergusaruben@gmail.com`
7. Save monitor

- [ ] **Step 4: Onboard first beta venue (manual)**

```bash
# Register venue owner account
curl -X POST https://YOUR_DOMAIN/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "owner@venue.com", "password": "temppass123", "name": "Имя Владельца"}'

# Get token
TOKEN=$(curl -s -X POST https://YOUR_DOMAIN/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "owner@venue.com", "password": "temppass123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create venue
curl -X POST https://YOUR_DOMAIN/venues \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Название Заведения", "slug": "venue-slug", "website_url": "https://venue-site.ru", "table_count": 10}'
```

- [ ] **Step 5: Trigger first parse job and verify worker picks it up**

```bash
VENUE_ID="<uuid from previous step>"
curl -X POST https://YOUR_DOMAIN/venues/$VENUE_ID/reparse \
  -H "Authorization: Bearer $TOKEN"

# Poll status
sleep 5
curl https://YOUR_DOMAIN/venues/$VENUE_ID/parse-status \
  -H "Authorization: Bearer $TOKEN"
```

Expected: `{"status": "done", "dishes_found": N, ...}` where N > 0.

- [ ] **Step 6: Commit final state**

```bash
git add .
git commit -m "docs: phase 4 launch plan complete"
```

---

## Beta Launch Criteria (Reference)

Before opening public registration, both columns must be fully checked:

| Technical | Product |
|---|---|
| ☐ 0 critical bugs for 48 h | ☐ ≥1 venue with live menu |
| ☐ CI/CD deploy succeeds on push | ☐ ≥10 real orders placed |
| ☐ `/health` green for 7 days | ☐ Owner operates dashboard without help |
| ☐ UptimeRobot uptime >99% | ☐ Playwright parser succeeded on ≥1 real JS site |

**Public launch actions:**
1. Confirm `POST /auth/register` has no invite gate
2. Write a short announcement post for Telegram channels: `Рестораторы`, `HoReCa автоматизация`, `Стартапы СНГ`
3. Tag the git commit: `git tag v1.0.0 && git push --tags`
