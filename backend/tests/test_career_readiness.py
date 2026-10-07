from fastapi.testclient import TestClient


def test_career_readiness_score_success(client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes):
    files = {"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    # Calculate ATS score first so resume has an ats_score
    client.post(f"/api/resumes/{resume_id}/ats-score", headers=auth_headers)

    # Request career readiness
    response = client.get(
        f"/api/career-readiness?resume_id={resume_id}&target_role=Backend%20Developer",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert 0 <= data["overall_score"] <= 100
    assert data["target_role"] == "Backend Developer"

    breakdown = data["breakdown"]
    assert 0 <= breakdown["skill_match"] <= 100
    assert 0 <= breakdown["resume_quality"] <= 100
    assert 0 <= breakdown["project_experience"] <= 100
    assert 0 <= breakdown["interview_readiness"] <= 100
    assert 0 <= breakdown["experience_relevance"] <= 100

    assert isinstance(data["strengths"], list)
    assert isinstance(data["areas_to_improve"], list)
    assert isinstance(data["recommendations"], list)
    assert len(data["strengths"]) > 0
    assert len(data["recommendations"]) > 0


def test_career_readiness_unauthorized_resume_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    other_user_auth_headers: dict[str, str],
    sample_pdf_bytes: bytes,
):
    files = {"file": ("user1.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    response = client.get(
        f"/api/career-readiness?resume_id={resume_id}&target_role=Backend%20Developer",
        headers=other_user_auth_headers,
    )
    assert response.status_code == 404


def test_career_readiness_missing_params_fails(client: TestClient, auth_headers: dict[str, str]):
    response = client.get("/api/career-readiness", headers=auth_headers)
    assert response.status_code == 422

