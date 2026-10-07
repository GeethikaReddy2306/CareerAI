from fastapi.testclient import TestClient


def test_job_analysis_success(client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes):
    # Upload resume
    files = {"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    jd = """
    We are looking for a Senior Python Backend Developer with strong expertise in FastAPI,
    PostgreSQL, REST APIs, Docker, and AWS. Experience with Microservices, Caching, and
    CI/CD pipelines is a huge plus.
    """

    response = client.post(
        "/api/job-analysis",
        json={"resume_id": resume_id, "job_description": jd},
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["resume_id"] == resume_id
    assert 0 <= data["match_score"] <= 100
    assert isinstance(data["matched_skills"], list)
    assert isinstance(data["partial_skills"], list)
    assert isinstance(data["missing_skills"], list)
    assert isinstance(data["important_keywords"], list)
    assert isinstance(data["interview_topics"], list)
    assert isinstance(data["recommendations"], list)

    # In our sample_pdf_bytes, Python, FastAPI, and PostgreSQL are present
    assert any("Python" in s for s in data["matched_skills"]) or any("FastAPI" in s for s in data["matched_skills"])


def test_job_analysis_empty_jd_fails(client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes):
    files = {"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    response = client.post(
        "/api/job-analysis",
        json={"resume_id": resume_id, "job_description": ""},
        headers=auth_headers,
    )
    assert response.status_code == 422 or response.status_code == 400


def test_job_analysis_invalid_resume_fails(client: TestClient, auth_headers: dict[str, str]):
    response = client.post(
        "/api/job-analysis",
        json={"resume_id": 99999, "job_description": "We need a Python developer with FastAPI."},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_job_analysis_unauthorized_resume_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    other_user_auth_headers: dict[str, str],
    sample_pdf_bytes: bytes,
):
    # User 1 uploads resume
    files = {"file": ("user1.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    # User 2 tries to run job analysis on User 1's resume
    response = client.post(
        "/api/job-analysis",
        json={"resume_id": resume_id, "job_description": "Senior Backend Developer with FastAPI"},
        headers=other_user_auth_headers,
    )
    assert response.status_code == 404

