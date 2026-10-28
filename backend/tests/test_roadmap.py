from fastapi.testclient import TestClient


def test_career_roadmap_generation_and_retrieval(
    client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes
):
    # Upload resume
    files = {"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    # Generate roadmap
    response = client.post(
        "/api/career/roadmap",
        json={"resume_id": resume_id, "target_role": "Backend Developer"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["resume_id"] == resume_id
    assert data["target_role"] == "Backend Developer"
    assert "current_level" in data
    assert isinstance(data["roadmap"], list)
    assert len(data["roadmap"]) >= 2

    # Verify phase structure
    for phase in data["roadmap"]:
        assert "phase" in phase
        assert "title" in phase
        assert "description" in phase
        assert isinstance(phase["skills"], list)
        assert isinstance(phase["topics"], list)
        assert isinstance(phase["projects"], list)
        assert phase["estimated_weeks"] >= 1
        assert phase["priority"] in ["High", "Medium", "Low"]

    # Verify existing skill is not taught as a basic
    roadmap_text = str(data["roadmap"]).lower()
    assert "learn python basics" not in roadmap_text
    assert "learn sql basics" not in roadmap_text

    # Retrieve roadmap via GET
    get_resp = client.get(f"/api/career/roadmap?resume_id={resume_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["resume_id"] == resume_id
    assert len(get_data["roadmap"]) == len(data["roadmap"])


def test_career_roadmap_unauthorized_resume_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    other_user_auth_headers: dict[str, str],
    sample_pdf_bytes: bytes,
):
    files = {"file": ("user1.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    response = client.post(
        "/api/career/roadmap",
        json={"resume_id": resume_id, "target_role": "Backend Developer"},
        headers=other_user_auth_headers,
    )
    assert response.status_code == 404

    get_resp = client.get(
        f"/api/career/roadmap?resume_id={resume_id}",
        headers=other_user_auth_headers,
    )
    assert get_resp.status_code == 404


def test_roadmap_progress_persists_for_its_owner(
    client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes
):
    upload = client.post("/api/resumes/upload", files={"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}, headers=auth_headers)
    created = client.post("/api/career/roadmap", json={"resume_id": upload.json()["id"], "target_role": "Backend Developer"}, headers=auth_headers)
    roadmap = created.json()
    skill = roadmap["roadmap"][0]["skills"][0]

    updated = client.patch(f"/api/career/roadmap/{roadmap['id']}/progress", json={"completed_skills": [skill, "Unrelated Skill"]}, headers=auth_headers)
    assert updated.status_code == 200
    assert updated.json()["completed_skills"] == [skill]

    saved = client.get(f"/api/career/roadmap?resume_id={upload.json()['id']}", headers=auth_headers)
    assert saved.json()["completed_skills"] == [skill]

