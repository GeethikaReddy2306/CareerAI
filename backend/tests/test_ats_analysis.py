from fastapi.testclient import TestClient
from app.services.ats_service import calculate_ats_score


def test_ats_service_score_range_and_breakdown():
    sample_text = """
    John Doe
    john.doe@example.com | 555-123-4567 | github.com/johndoe
    
    Professional Summary
    Experienced software engineer specializing in backend systems and cloud platforms.
    
    Skills
    Python, FastAPI, Docker, PostgreSQL, Kubernetes, AWS, Git, Redis, Linux
    
    Work Experience
    Senior Developer at ACME Corp
    - Engineered high-throughput REST APIs and reduced latency by 30%.
    - Deployed containerized applications with Docker and Kubernetes.
    
    Projects
    Career Platform: Built scalable microservice architecture using Python and FastAPI.
    
    Education
    B.S. in Computer Science, 2021
    """
    result = calculate_ats_score(sample_text)
    assert 0 <= result.score <= 100
    assert result.breakdown.keyword_relevance >= 0
    assert result.breakdown.structure >= 0
    assert result.breakdown.required_sections >= 0
    assert result.breakdown.skills_clarity >= 0
    assert result.breakdown.experience_quality >= 0
    assert result.breakdown.formatting >= 0
    assert "Skills" in result.detected_sections
    assert "Education" in result.detected_sections
    assert isinstance(result.suggestions, list)
    assert result.analysis_mode == "deterministic"
    assert result.improvements
    for improvement in result.improvements:
        assert improvement.issue and improvement.why_it_matters and improvement.suggested_correction
    assert isinstance(result.categories, list)
    names = {c.name for c in result.categories}
    assert {"Quantifying Impact", "Repetition", "Spelling & Grammar", "Bullets Consistency"} <= names


def test_keyword_matching_does_not_use_substrings():
    text = """
    Jane Doe
    jane@example.com

    Skills
    JavaScript, algorithms, HTML, CSS, Express, Redux, Mongoose, Jest

    Experience
    - Developed a javascript algorithm tutorial site.
    """
    result = calculate_ats_score(text)
    # "go" must not match inside "algorithm"; "java" must not match inside "javascript"
    from app.services.ats_service import _keyword_present
    assert not _keyword_present("go", "algorithm")
    assert not _keyword_present("java", "javascript")
    assert _keyword_present("javascript", "javascript, html")
    assert _keyword_present("c++", "experience with c++ and rust")
    assert _keyword_present("node.js", "built apis with node.js")
    assert result.breakdown.keyword_relevance > 0


def test_ats_score_endpoint(client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes):
    # Upload resume
    files = {"file": ("ats_test.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    # Request ATS Score
    ats_resp = client.post(f"/api/resumes/{resume_id}/ats-score", headers=auth_headers)
    assert ats_resp.status_code == 200
    data = ats_resp.json()

    assert 0 <= data["score"] <= 100
    assert "breakdown" in data
    assert "keyword_relevance" in data["breakdown"]
    assert "structure" in data["breakdown"]
    assert "required_sections" in data["breakdown"]
    assert "skills_clarity" in data["breakdown"]
    assert "experience_quality" in data["breakdown"]
    assert "formatting" in data["breakdown"]
    assert isinstance(data["detected_sections"], list)
    assert isinstance(data["missing_sections"], list)
    assert isinstance(data["suggestions"], list)
    assert isinstance(data["improvements"], list)
    assert data["improvements"]
    assert isinstance(data["categories"], list)
    assert "ai_review" in data
    assert "overall_feedback" in data["ai_review"]
    assert data["ai_review"]["status"] in ("available", "unavailable")


def test_ai_resume_analysis_and_caching(
    client: TestClient, auth_headers: dict[str, str], sample_pdf_bytes: bytes
):
    # Upload resume
    files = {"file": ("ai_test.pdf", sample_pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/resumes/upload", files=files, headers=auth_headers)
    resume_id = upload_resp.json()["id"]

    # 1. Run AI analysis
    analyze_resp = client.post(f"/api/resumes/{resume_id}/analyze", headers=auth_headers)
    assert analyze_resp.status_code == 200
    analysis_data = analyze_resp.json()
    assert analysis_data["success"] is True

    record = analysis_data["data"]
    assert record["resume_id"] == resume_id
    assert isinstance(record["skills"], list)
    assert "Python" in record["skills"] or len(record["skills"]) > 0
    assert isinstance(record["education"], list)
    assert isinstance(record["projects"], list)
    assert isinstance(record["strengths"], list)
    assert isinstance(record["suggested_roles"], list)
    assert record["experience_level"] in ["Student", "Fresher", "Junior", "Mid-Level", "Senior"]

    # 2. Call analyze again without force_refresh (should return cached analysis)
    cached_resp = client.post(f"/api/resumes/{resume_id}/analyze", headers=auth_headers)
    assert cached_resp.status_code == 200
    cached_data = cached_resp.json()
    assert "existing" in cached_data["message"].lower()

    # 3. Call analyze with force_refresh=true
    force_resp = client.post(
        f"/api/resumes/{resume_id}/analyze?force_refresh=true", headers=auth_headers
    )
    assert force_resp.status_code == 200
    assert "successfully" in force_resp.json()["message"].lower()

    # 4. Get analysis via GET endpoint
    get_resp = client.get(f"/api/resumes/{resume_id}/analysis", headers=auth_headers)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["resume_id"] == resume_id
    assert get_data["summary"] is not None

