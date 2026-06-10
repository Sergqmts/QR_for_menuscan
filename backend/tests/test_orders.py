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
