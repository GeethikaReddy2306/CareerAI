from fastapi.testclient import TestClient


def test_interview_questions_generation_and_retrieval(
    client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes
):
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
    client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes
):
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

