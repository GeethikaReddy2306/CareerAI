from fastapi.testclient import TestClient

from app.services import job_analysis_service


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


def test_skill_classification_is_a_disjoint_partition(monkeypatch):
    extracted = job_analysis_service.AIJobExtractionSchema(
        required_skills=["Python", "FastAPI", "Docker", "AWS"],
        important_keywords=["Python", "FastAPI", "Docker", "AWS"],
        interview_topics=["Python"],
        recommendations=[],
    )
    monkeypatch.setattr(job_analysis_service, "call_structured_ai", lambda **_: extracted)
    profile = {
        "skills": ["Python", "FastAPI", "Docker"],
        "projects": [{"name": "API", "description": "Built a Python FastAPI service", "technologies": ["Python", "FastAPI"]}],
        "work_experience": [{"company": "Acme", "role": "Engineer", "responsibilities": ["Maintained FastAPI endpoints"]}],
        "experience_level": "Mid-level",
    }

    result = job_analysis_service.analyze_job_description(
        profile, "Backend role requiring Python, FastAPI, Docker, and AWS."
    )

    categories = [
        set(result["matched_skills"]),
        set(result["partial_skills"]),
        set(result["missing_skills"]),
    ]
    assert not categories[0].intersection(categories[1])
    assert not categories[0].intersection(categories[2])
    assert not categories[1].intersection(categories[2])
    assert "Docker" in result["partial_skills"]  # listed but not evidenced in project/work material
    assert "AWS" in result["missing_skills"]

