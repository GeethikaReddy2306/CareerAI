from fastapi.testclient import TestClient
from app.main import app


def test_full_acceptance_criteria_flow(client: TestClient, sample_pdf_bytes: bytes):
    """Verifies the complete Step 1 to Step 10 lifecycle:

    REGISTER -> LOGIN -> GET CURRENT USER -> UPLOAD RESUME PDF ->
    PDF TEXT EXTRACTION -> RESUME IN DB -> AI RESUME ANALYSIS ->
    STRUCTURED PROFILE STORED -> ATS SCORE -> ATS BREAKDOWN + SUGGESTIONS.
    """
    # 1. REGISTER
    reg_payload = {
        "name": "Grace Hopper",
        "email": "grace.hopper@example.com",
        "password": "compiler_pioneer_1952",
    }
    reg_resp = client.post("/api/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201, reg_resp.text
    user_info = reg_resp.json()["data"]
    assert user_info["email"] == "grace.hopper@example.com"
    user_id = user_info["id"]

    # 2. LOGIN
    login_resp = client.post(
        "/api/auth/login",
        json={"email": reg_payload["email"], "password": reg_payload["password"]},
    )
    assert login_resp.status_code == 200, login_resp.text
    login_data = login_resp.json()
    assert "access_token" in login_data
    token = login_data["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 3. GET CURRENT USER
    me_resp = client.get("/api/auth/me", headers=auth_headers)
    assert me_resp.status_code == 200, me_resp.text
    me_data = me_resp.json()
    assert me_data["id"] == user_id
    assert me_data["email"] == "grace.hopper@example.com"

    # 4. UPLOAD RESUME PDF & 5. PDF TEXT EXTRACTION
    files = {"file": ("grace_resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    assert upload_resp.status_code == 201, upload_resp.text
    upload_data = upload_resp.json()
    assert upload_data["filename"] == "grace_resume.pdf"
    assert upload_data["text_length"] > 100
    resume_id = upload_data["id"]

    # 6. RESUME STORED IN DATABASE & RETRIEVABLE
    detail_resp = client.get(f"/api/resumes/{resume_id}", headers=auth_headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail_data = detail_resp.json()
    assert detail_data["id"] == resume_id
    assert "Python" in detail_data["extracted_text"]

    # 7. AI RESUME ANALYSIS & 8. STRUCTURED PROFILE STORED
    ai_resp = client.post(f"/api/resumes/{resume_id}/analyze", headers=auth_headers)
    assert ai_resp.status_code == 200, ai_resp.text
    ai_data = ai_resp.json()
    assert ai_data["success"] is True
    profile = ai_data["data"]
    assert profile["resume_id"] == resume_id
    assert len(profile["skills"]) > 0
    assert len(profile["suggested_roles"]) > 0
    assert profile["experience_level"] in ["Student", "Fresher", "Junior", "Mid-Level", "Senior"]

    # 9. ATS SCORE & 10. ATS BREAKDOWN + SUGGESTIONS
    ats_resp = client.post(f"/api/resumes/{resume_id}/ats-score", headers=auth_headers)
    assert ats_resp.status_code == 200, ats_resp.text
    ats_data = ats_resp.json()
    assert 0 <= ats_data["score"] <= 100
    breakdown = ats_data["breakdown"]
    assert "keyword_relevance" in breakdown
    assert "structure" in breakdown
    assert "required_sections" in breakdown
    assert "skills_clarity" in breakdown
    assert "experience_quality" in breakdown
    assert "formatting" in breakdown
    assert isinstance(ats_data["suggestions"], list)
    assert isinstance(ats_data["detected_sections"], list)

    # 11. VERIFY FULL ANALYSIS GET ENDPOINT
    final_analysis_resp = client.get(f"/api/resumes/{resume_id}/analysis", headers=auth_headers)
    assert final_analysis_resp.status_code == 200, final_analysis_resp.text
    final_data = final_analysis_resp.json()
    assert final_data["ats_score"] == ats_data["score"]
    assert final_data["summary"] is not None

