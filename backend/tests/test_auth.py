from fastapi.testclient import TestClient


def test_user_registration_success(client: TestClient):
    payload = {
        "name": "Alice Developer",
        "email": "alice@example.com",
        "password": "securepassword123",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Alice Developer"
    assert data["data"]["email"] == "alice@example.com"
    assert "id" in data["data"]
    # Ensure password hash is NEVER leaked
    assert "password" not in data["data"]
    assert "password_hash" not in data["data"]


def test_duplicate_registration_fails(client: TestClient):
    payload = {
        "name": "Alice Developer",
        "email": "alice@example.com",
        "password": "securepassword123",
    }
    # First registration
    resp1 = client.post("/api/auth/register", json=payload)
    assert resp1.status_code == 201

    # Duplicate registration
    resp2 = client.post("/api/auth/register", json=payload)
    assert resp2.status_code == 400
    data = resp2.json()
    assert data["success"] is False
    assert "already registered" in data["message"].lower()


def test_login_success(client: TestClient):
    # Register user
    client.post(
        "/api/auth/register",
        json={"name": "Bob", "email": "bob@example.com", "password": "mypassword123"},
    )

    # Login
    response = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "mypassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"].lower() == "bearer"
    assert len(data["access_token"]) > 20


def test_login_invalid_password_fails(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"name": "Charlie", "email": "charlie@example.com", "password": "correctpassword"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "charlie@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False


def test_login_nonexistent_email_fails(client: TestClient):
    response = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "somepassword"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False


def test_get_current_user_me(client: TestClient, auth_headers: dict[str, str]):
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "primary@example.com"
    assert data["name"] == "Primary User"
    assert "id" in data


def test_protected_endpoint_without_token_fails(client: TestClient):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_protected_endpoint_with_invalid_token_fails(client: TestClient):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token_abc"})
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False

