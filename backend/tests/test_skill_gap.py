from fastapi.testclient import TestClient
from app.services.skill_gap_service import normalize_skill


def test_skill_normalization_utility():
    assert normalize_skill("ReactJS") == "React"
    assert normalize_skill("React.js") == "React"
    assert normalize_skill("react js") == "React"
    assert normalize_skill("NodeJS") == "Node.js"
    assert normalize_skill("node.js") == "Node.js"
    assert normalize_skill("postgres") == "PostgreSQL"
    assert normalize_skill("postgresql") == "PostgreSQL"
    assert normalize_skill("golang") == "Go"
    assert normalize_skill("k8s") == "Kubernetes"
    assert normalize_skill("docker") == "Docker"
    assert normalize_skill("JS") == "JavaScript"


def test_java_does_not_match_javascript():
    from app.services.skill_normalization import skill_in_text
    assert skill_in_text("JavaScript", "Built a JavaScript application")
    assert not skill_in_text("Java", "Built a JavaScript application")


def test_skill_gap_success_default_role(client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes):
    files = {"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    response = client.post(
        "/api/skill-gap",
        json={"resume_id": resume_id, "target_role": "Backend Developer"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["target_role"] == "Backend Developer"
    assert isinstance(data["strong"], list)
    assert isinstance(data["intermediate"], list)
    assert isinstance(data["weak"], list)
    assert isinstance(data["missing"], list)
    assert isinstance(data["prioritized_skills"], list)

    # In sample_pdf_bytes, candidate has Python and FastAPI
    assert "Python" in data["strong"] or "Python" in data["intermediate"]
    # Check prioritization format
    if data["prioritized_skills"]:
        p_item = data["prioritized_skills"][0]
        assert "skill" in p_item
        assert p_item["category"] in ["Strong", "Intermediate", "Weak", "Missing"]
        assert p_item["priority"] in ["High", "Medium", "Low"]
        assert len(p_item["reason"]) > 0


def test_skill_gap_with_custom_target_skills(client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes):
    files = {"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    custom_skills = ["Python", "FastAPI", "ReactJS", "NodeJS", "Terraform"]
    response = client.post(
        "/api/skill-gap",
        json={
            "resume_id": resume_id,
            "target_role": "Full Stack Engineer",
            "target_skills": custom_skills,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    all_evaluated = data["strong"] + data["intermediate"] + data["weak"] + data["missing"]
    # Verify ReactJS normalized to React and NodeJS to Node.js
    assert "React" in all_evaluated
    assert "Node.js" in all_evaluated


def test_skill_gap_missing_target_role_fails(client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes):
    files = {"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    response = client.post(
        "/api/skill-gap",
        json={"resume_id": resume_id, "target_role": ""},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_skill_gap_unauthorized_resume_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    other_user_auth_headers: dict[str, str],
    sample_pdf_bytes: bytes,
):
    files = {"file": ("user1.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    response = client.post(
        "/api/skill-gap",
        json={"resume_id": resume_id, "target_role": "Backend Developer"},
        headers=other_user_auth_headers,
    )
    assert response.status_code == 404

