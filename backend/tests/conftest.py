import io
from pathlib import Path
import tempfile
from typing import Generator
import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

# In-memory SQLite engine for tests
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session for tests."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Test client with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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

