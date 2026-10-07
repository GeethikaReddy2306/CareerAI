import io
from fastapi.testclient import TestClient


def test_resume_upload_success(client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes):
    files = {"file": ("my_resume.pdf", sample_pdf_bytes, "application/pdf")}
    response = client.post("/api/resumes/upload", files=files, headers=auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "my_resume.pdf"
    assert data["message"] == "Resume uploaded and parsed successfully"
    assert data["text_length"] > 100
    assert "id" in data


def test_resume_upload_invalid_extension_fails(client: TestClient, auth_headers: dict[str, str]):
    text_content = b"This is a plain text resume."
    files = {"file": ("resume.txt", text_content, "application/pdf")}
    response = client.post("/api/resumes/upload", files=files, headers=auth_headers)

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "extension" in data["message"].lower()


def test_resume_upload_invalid_mime_type_fails(client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes):
    files = {"file": ("resume.pdf", sample_pdf_bytes, "text/plain")}
    response = client.post("/api/resumes/upload", files=files, headers=auth_headers)

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "content type" in data["message"].lower()


def test_resume_upload_corrupted_pdf_fails(client: TestClient, auth_headers: dict[str, str]):
    files = {"file": ("bad.pdf", b"%PDF-1.4 not a real pdf %%%%", "application/pdf")}
    response = client.post("/api/resumes/upload", files=files, headers=auth_headers)

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "pdf" in data["message"].lower()
    assert "traceback" not in data["message"].lower()
    assert "uploads" not in data["message"].lower()


def test_resume_upload_oversized_file_fails(client: TestClient, auth_headers: dict[str, str]):
    # 6 MB dummy payload
    oversized_bytes = b"0" * (6 * 1024 * 1024)
    files = {"file": ("large_resume.pdf", oversized_bytes, "application/pdf")}
    response = client.post("/api/resumes/upload", files=files, headers=auth_headers)

    assert response.status_code == 413
    data = response.json()
    assert data["success"] is False
    assert "exceeds" in data["message"].lower()


def test_list_and_get_resumes(client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes):
    # Upload resume
    files = {"file": ("sample.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    assert upload_resp.status_code == 201
    resume_id = upload_resp.json()["id"]

    # List resumes
    list_resp = client.get("/api/resumes", headers=auth_headers)
    assert list_resp.status_code == 200
    resumes = list_resp.json()
    assert len(resumes) >= 1
    assert any(r["id"] == resume_id for r in resumes)

    # Get single resume
    detail_resp = client.get(f"/api/resumes/{resume_id}", headers=auth_headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == resume_id
    assert detail["extracted_text"] is not None
    assert "Python" in detail["extracted_text"]


def test_resume_ownership_isolation(
    client: TestClient,
    auth_headers: dict[str, str],
    other_user_auth_headers: dict[str, str],
    sample_pdf_bytes: bytes,
):
    # Primary user uploads resume
    files = {"file": ("user_a_resume.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    assert upload_resp.status_code == 201
    resume_id = upload_resp.json()["id"]

    # Secondary user attempts to get Primary user's resume
    get_resp = client.get(f"/api/resumes/{resume_id}", headers=other_user_auth_headers)
    assert get_resp.status_code == 404
    assert get_resp.json()["success"] is False

    # Secondary user attempts to delete Primary user's resume
    del_resp = client.delete(f"/api/resumes/{resume_id}", headers=other_user_auth_headers)
    assert del_resp.status_code == 404
    assert del_resp.json()["success"] is False


def test_delete_resume_success(client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes):
    # Upload
    files = {"file": ("to_delete.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    # Delete
    del_resp = client.delete(f"/api/resumes/{resume_id}", headers=auth_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # Verify 404 on subsequent get
    get_resp = client.get(f"/api/resumes/{resume_id}", headers=auth_headers)
    assert get_resp.status_code == 404

