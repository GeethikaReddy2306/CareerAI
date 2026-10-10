import io
from pathlib import Path
import tempfile
from typing import Generator
import mongomock
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db, set_test_db
from app.main import app


@pytest.fixture
def test_db():
    """Create an isolated in-memory MongoDB database for testing."""
    client = mongomock.MongoClient()
    db = client[settings.MONGODB_DATABASE]
    # Ensure indexes in mock DB
    db["users"].create_index("email", unique=True)
    db["resumes"].create_index("user_id")
    db["resume_analyses"].create_index("resume_id", unique=True)
    return db


@pytest.fixture
def client(test_db) -> Generator[TestClient, None, None]:
    """Test client with overridden get_db dependency using mongomock."""
    set_test_db(test_db)
    app.dependency_overrides[get_db] = lambda: test_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    set_test_db(None)


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Generate a realistic test resume PDF in memory using PyMuPDF."""
    doc = pymupdf.open()
    page = doc.new_page()

    resume_text = """John Doe
john.doe@example.com | +1 555-0199 | github.com/johndoe | linkedin.com/in/johndoe

PROFESSIONAL SUMMARY
Results-driven Senior Backend Engineer with 5+ years of experience designing high-scale REST APIs,
distributed microservices, and database systems.

SKILLS
Programming: Python, JavaScript, TypeScript, SQL, Go
Frameworks & Tools: FastAPI, Django, PostgreSQL, Docker, Kubernetes, AWS, Git, Redis, Linux, Pytest

WORK EXPERIENCE
Senior Backend Developer - TechCorp Inc. (2021 - Present)
- Architected and deployed scalable REST APIs using FastAPI and PostgreSQL, serving 500,000+ daily active users.
- Optimized database queries and indexed tables, reducing P99 latency by 35%.
- Led a team of 4 engineers, spearheading CI/CD automation with GitHub Actions and Docker.

PROJECTS
Career Intelligence Platform (Python, FastAPI, Docker)
- Built an automated career coaching backend with structured OpenAI analysis and deterministic ATS scoring.
- Implemented JWT authentication and PyMuPDF document text extraction pipeline.

EDUCATION
Bachelor of Science in Computer Science
State University, 2020

CERTIFICATIONS
- AWS Certified Solutions Architect Associate
"""
    page.insert_text((50, 60), resume_text, fontsize=10)
    pdf_stream = io.BytesIO()
    doc.save(pdf_stream)
    doc.close()
    return pdf_stream.getvalue()


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Register and log in a primary test user, returning Bearer auth headers."""
    user_payload = {
        "name": "Primary User",
        "email": "primary@example.com",
        "password": "password123",
    }
    reg_resp = client.post("/api/auth/register", json=user_payload)
    assert reg_resp.status_code == 201

    login_resp = client.post(
        "/api/auth/login",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_user_auth_headers(client: TestClient) -> dict[str, str]:
    """Register and log in a secondary test user for isolation testing."""
    user_payload = {
        "name": "Secondary User",
        "email": "secondary@example.com",
        "password": "password456",
    }
    reg_resp = client.post("/api/auth/register", json=user_payload)
    assert reg_resp.status_code == 201

    login_resp = client.post(
        "/api/auth/login",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
