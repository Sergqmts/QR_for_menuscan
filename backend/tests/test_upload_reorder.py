import pytest
import uuid as uuid_mod
from unittest.mock import patch


async def _setup(client):
    email = f"ur_{uuid_mod.uuid4().hex[:6]}@test.ru"
    r = await client.post("/auth/register", json={"email": email, "password": "Pass123", "full_name": "U"})
    token = r.json()["access_token"]
    vr = await client.post("/venues", json={"name": f"V{uuid_mod.uuid4().hex[:4]}", "table_count": 0}, headers={"Authorization": f"Bearer {token}"})
    venue = vr.json()["venue"]
    cr = await client.post(f"/venues/{venue['id']}/categories", json={"name": "A", "slug": "a"}, headers={"Authorization": f"Bearer {token}"})
    cat_a = cr.json()
    cr2 = await client.post(f"/venues/{venue['id']}/categories", json={"name": "B", "slug": "b", "sort_order": 1}, headers={"Authorization": f"Bearer {token}"})
    cat_b = cr2.json()
    dr = await client.post(f"/venues/{venue['id']}/dishes", json={"category_id": cat_a["id"], "name": "Суп", "price": 200}, headers={"Authorization": f"Bearer {token}"})
    dish = dr.json()
    return token, venue, cat_a, cat_b, dish


@pytest.mark.asyncio
async def test_category_reorder(client):
    token, venue, cat_a, cat_b, dish = await _setup(client)
    r = await client.patch(
        f"/venues/{venue['id']}/categories/reorder",
        json={"category_ids": [cat_b["id"], cat_a["id"]]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    cats = (await client.get(f"/venues/{venue['id']}/categories", headers={"Authorization": f"Bearer {token}"})).json()["categories"]
    assert cats[0]["id"] == cat_b["id"]
    assert cats[1]["id"] == cat_a["id"]


@pytest.mark.asyncio
async def test_upload_url_returns_presigned(client):
    token, venue, cat_a, cat_b, dish = await _setup(client)
    fake_upload_url = "https://minio.example.com/presigned-put"
    fake_image_url = f"https://minio.example.com/menuscan/dishes/{venue['id']}/{dish['id']}.jpg"
    with patch("app.api.dishes.get_presigned_upload_url", return_value=(fake_upload_url, fake_image_url)):
        r = await client.post(
            f"/venues/{venue['id']}/dishes/{dish['id']}/upload-url",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    data = r.json()
    assert "upload_url" in data
    assert "image_url" in data
    assert str(dish["id"]) in data["image_url"]


@pytest.mark.asyncio
async def test_upload_url_wrong_venue(client):
    token, venue, cat_a, cat_b, dish = await _setup(client)
    r = await client.post(
        f"/venues/{uuid_mod.uuid4()}/dishes/{dish['id']}/upload-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
