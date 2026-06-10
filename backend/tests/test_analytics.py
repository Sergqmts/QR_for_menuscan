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
    assert r.status_code == 401
