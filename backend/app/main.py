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
from app.api.analytics import router as analytics_router
from app.core.database import AsyncSessionLocal

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
app.include_router(analytics_router)


@app.websocket("/ws/table/{table_id}")
async def websocket_table(
    websocket: WebSocket,
    table_id: uuid_mod.UUID,
    guest_id: str = "",
    venue_id: str = "",
):
    from app.ws.table import ws_table_handler
    async with AsyncSessionLocal() as db:
        await ws_table_handler(websocket, table_id, guest_id, venue_id, db)


@app.websocket("/ws/kitchen/{venue_id}")
async def websocket_kitchen(
    websocket: WebSocket,
    venue_id: uuid_mod.UUID,
    token: str = "",
):
    from app.ws.kitchen import ws_kitchen_handler
    async with AsyncSessionLocal() as db:
        await ws_kitchen_handler(websocket, venue_id, token, db)


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
