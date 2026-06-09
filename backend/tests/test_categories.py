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
