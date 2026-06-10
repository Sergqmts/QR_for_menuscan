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
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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
        assert len(msg["payload"]["cart"]) >= 1


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
