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
