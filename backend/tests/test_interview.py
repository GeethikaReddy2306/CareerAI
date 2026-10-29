import pytest
from fastapi.testclient import TestClient

from app.services import ai_resume_analyzer, interview_service


@pytest.fixture(autouse=True)
def _disable_runtime_demo_mode(monkeypatch):
    """Endpoint tests choose their provider condition explicitly."""
    monkeypatch.setattr(interview_service.settings, "INTERVIEW_DEMO_MODE", False)


def test_interview_questions_generation_and_retrieval(
    client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes, monkeypatch
):
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (None, "timeout"))
    monkeypatch.setattr(ai_resume_analyzer, "is_openai_configured", lambda: False)
    # Upload resume
    files = {"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    requested_count = 14
    response = client.post(
        "/api/interview/questions",
        json={
            "resume_id": resume_id,
            "target_role": "Backend Developer",
            "question_count": requested_count,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert "questions" in data
    questions = data["questions"]
    assert len(questions) == requested_count
    assert data["generation_mode"] == "profile_based"
    assert data["failure_category"] == "timeout"

    categories_found = {q["category"] for q in questions}
    # Verify core categories
    expected_categories = {
        "Technical", "Resume Based", "Project Based", "Role Specific",
        "Skill Gap Based", "Behavioral", "HR"
    }
    for cat in expected_categories:
        assert cat in categories_found, f"Expected category {cat} missing from generated questions"

    for q in questions:
        assert len(q["question"]) > 10
        assert q["difficulty"] in ["Easy", "Medium", "Hard"]
        assert len(q["topic"]) > 0

    # Retrieve saved questions via GET
    get_resp = client.get(f"/api/interview/questions?resume_id={resume_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert len(get_data["questions"]) == requested_count


def test_interview_questions_with_job_description(
    client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes, monkeypatch
):
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (None, "timeout"))
    monkeypatch.setattr(ai_resume_analyzer, "is_openai_configured", lambda: False)
    files = {"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    jd = "Looking for a Python developer with FastAPI and Kubernetes experience."
    response = client.post(
        "/api/interview/questions",
        json={
            "resume_id": resume_id,
            "target_role": "Cloud Backend Engineer",
            "job_description": jd,
            "question_count": 7,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert len(data["questions"]) == 7
    normalized = {" ".join(question["question"].lower().split()) for question in data["questions"]}
    assert len(normalized) == len(data["questions"])


def test_explicit_demo_mode_generates_and_persists_a_role_specific_session(
    client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes, monkeypatch
):
    monkeypatch.setattr(interview_service.settings, "INTERVIEW_DEMO_MODE", True)
    monkeypatch.setattr(ai_resume_analyzer, "is_openai_configured", lambda: False)
    upload_resp = client.post(
        "/api/resumes/upload",
        files={"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")},
        headers=auth_headers,
    )

    response = client.post(
        "/api/interview/questions",
        json={
            "resume_id": upload_resp.json()["id"],
            "target_role": "Backend Developer",
            "job_description": "Build reliable Python APIs with FastAPI and PostgreSQL.",
            "question_count": 5,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["generation_mode"] == "demo"
    assert data["session_id"]
    assert len(data["questions"]) == 5
    assert data["generation_notice"].startswith("Demo mode — not AI-generated.")

    restored = client.get(f"/api/interview/sessions/{data['session_id']}", headers=auth_headers)
    assert restored.status_code == 200
    assert restored.json()["generation_mode"] == "demo"


def test_interview_questions_unauthorized_resume_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    other_user_auth_headers: dict[str, str],
    sample_pdf_bytes: bytes,
):
    files = {"file": ("user1.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    response = client.post(
        "/api/interview/questions",
        json={"resume_id": resume_id, "target_role": "Backend Developer"},
        headers=other_user_auth_headers,
    )
    assert response.status_code == 404

    get_resp = client.get(
        f"/api/interview/questions?resume_id={resume_id}",
        headers=other_user_auth_headers,
    )
    assert get_resp.status_code == 404

