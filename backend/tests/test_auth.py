import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post("/auth/register", json={
        "email": "owner@test.ru",
        "password": "SecurePass123",
        "full_name": "Тест Тестов"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["email"] == "owner@test.ru"
    assert "access_token" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@test.ru", "password": "Pass123", "full_name": "A"}
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/auth/register", json={
        "email": "login@test.ru", "password": "Pass123", "full_name": "B"
    })
    response = await client.post("/auth/login", json={
        "email": "login@test.ru", "password": "Pass123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "email": "wrongpass@test.ru", "password": "Correct123", "full_name": "C"
    })
    response = await client.post("/auth/login", json={
        "email": "wrongpass@test.ru", "password": "Wrong123"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client):
    reg = await client.post("/auth/register", json={
        "email": "me@test.ru", "password": "Pass123", "full_name": "D"
    })
    token = reg.json()["access_token"]
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@test.ru"
