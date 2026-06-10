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
