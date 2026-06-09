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
