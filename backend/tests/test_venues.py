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
