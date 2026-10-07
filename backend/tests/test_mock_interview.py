def _auth_headers(client):
    client.post(
        "/api/auth/register",
        json={"name": "Mock User", "email": "mockuser@example.com", "password": "secret12"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": "mockuser@example.com", "password": "secret12"},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_evaluate_mock_answer_requires_auth(client):
    response = client.post(
        "/api/interview/evaluate",
        json={
            "question": "Explain REST APIs.",
            "answer": "REST is an architectural style using HTTP verbs.",
            "category": "Technical",
            "topic": "REST",
        },
    )
    assert response.status_code in (401, 403)


def test_evaluate_mock_answer_returns_score(client):
    headers = _auth_headers(client)
    response = client.post(
        "/api/interview/evaluate",
        headers=headers,
        json={
            "question": "How do you design a scalable REST API in FastAPI?",
            "answer": (
                "I would split services by bounded context, use async endpoints, "
                "add connection pooling, cache hot reads in Redis, and measure p95 latency. "
                "For example, in a billing project we reduced timeouts by adding retries and circuit breakers."
            ),
            "category": "Technical",
            "topic": "FastAPI",
            "target_role": "Backend Developer",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["score"] <= 100
    assert body["verdict"] in ("Strong", "Adequate", "Needs Work")
    assert body["feedback"]
