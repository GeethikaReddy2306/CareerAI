from fastapi.testclient import TestClient


def test_complete_platform_lifecycle_flow(client: TestClient, sample_pdf_bytes: bytes):
    """Complete end-to-end integration flow verifying all Phase 1 and Phase 2 features:

    REGISTER -> LOGIN -> UPLOAD RESUME -> PARSE -> AI ANALYSIS -> ATS SCORE ->
    JOB ANALYSIS -> SKILL GAP -> CAREER READINESS -> ROADMAP -> INTERVIEW QUESTIONS.
    """
    # 1. REGISTER
    reg_resp = client.post(
        "/api/auth/register",
        json={"name": "Ada Lovelace", "email": "ada.lovelace@example.com", "password": "analytical_engine_1843"},
    )
    assert reg_resp.status_code == 201

    # 2. LOGIN
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "ada.lovelace@example.com", "password": "analytical_engine_1843"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 3. GET /me
    me_resp = client.get("/api/auth/me", headers=auth_headers)
    assert me_resp.status_code == 200

    # 4. UPLOAD RESUME & PARSE PDF
    files = {"file": ("ada_resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    assert upload_resp.status_code == 201
    resume_id = upload_resp.json()["id"]

    # 5. AI RESUME ANALYSIS
    ai_resp = client.post(f"/api/resumes/{resume_id}/analyze", headers=auth_headers)
    assert ai_resp.status_code == 200
    assert ai_resp.json()["success"] is True

    # 6. ATS SCORE
    ats_resp = client.post(f"/api/resumes/{resume_id}/ats-score", headers=auth_headers)
    assert ats_resp.status_code == 200
    assert 0 <= ats_resp.json()["score"] <= 100

    # 7. JOB ANALYSIS (Resume + JD)
    jd_text = """
    Senior Python Backend Engineer at NextGen Cloud Inc.
    Requirements:
    - 4+ years of Python and FastAPI or Django development.
    - PostgreSQL database design and query tuning.
    - Docker containerization and Kubernetes orchestration.
    - AWS cloud architecture and microservices design.
    """
    job_resp = client.post(
        "/api/job-analysis",
        json={"resume_id": resume_id, "job_description": jd_text},
        headers=auth_headers,
    )
    assert job_resp.status_code == 201
    job_data = job_resp.json()
    assert 0 <= job_data["match_score"] <= 100
    assert len(job_data["matched_skills"]) > 0

    # 8. SKILL GAP ANALYSIS
    gap_resp = client.post(
        "/api/skill-gap",
        json={"resume_id": resume_id, "target_role": "Backend Developer"},
        headers=auth_headers,
    )
    assert gap_resp.status_code == 200
    gap_data = gap_resp.json()
    # A listed skill without project/work evidence is intermediate, not falsely strong.
    assert len(gap_data["strong"]) + len(gap_data["intermediate"]) > 0
    assert len(gap_data["missing"]) > 0
    assert len(gap_data["prioritized_skills"]) > 0

    # 9. CAREER READINESS SCORE
    readiness_resp = client.get(
        f"/api/career-readiness?resume_id={resume_id}&target_role=Backend%20Developer",
        headers=auth_headers,
    )
    assert readiness_resp.status_code == 200
    readiness_data = readiness_resp.json()
    assert 0 <= readiness_data["overall_score"] <= 100
    assert readiness_data["breakdown"]["skill_match"] >= 0

    # 10. PERSONALIZED ROADMAP
    roadmap_resp = client.post(
        "/api/career/roadmap",
        json={"resume_id": resume_id, "target_role": "Backend Developer"},
        headers=auth_headers,
    )
    assert roadmap_resp.status_code == 201
    roadmap_data = roadmap_resp.json()
    assert len(roadmap_data["roadmap"]) >= 2

    # 11. PERSONALIZED INTERVIEW QUESTIONS
    interview_resp = client.post(
        "/api/interview/questions",
        json={"resume_id": resume_id, "target_role": "Backend Developer", "question_count": 14},
        headers=auth_headers,
    )
    assert interview_resp.status_code == 201
    interview_data = interview_resp.json()
    assert len(interview_data["questions"]) == 14

