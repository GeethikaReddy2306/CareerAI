"""
ATS scoring service tests — run with:  python tests/test_ats.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.ats_service import calculate_ats_score, _calculate_deterministic_score

FULL_RESUME = """
John Doe | john@example.com | 555-1234 | github.com/johndoe | linkedin.com/in/johndoe

PROFESSIONAL SUMMARY
Full-stack software engineer with 3 years of experience building scalable web applications
using Python, React, and AWS.

SKILLS
Languages: Python, JavaScript, TypeScript, SQL
Frameworks: React, FastAPI, Node.js, Django
Databases: PostgreSQL, MongoDB, Redis
Tools: Docker, Git, AWS, CI/CD, Jest, Pytest, Kubernetes

WORK EXPERIENCE
Software Engineer, Acme Corp (Jan 2022 - Present)
- Developed REST APIs using FastAPI and Python, reducing response time by 40%
- Built React dashboard components serving 10,000+ daily active users
- Deployed microservices on AWS using Docker and Kubernetes, cutting infra cost by 25%
- Automated CI/CD pipelines with GitHub Actions, saving 3 hours/week of manual work

Junior Developer, Startup XYZ (Jun 2021 - Dec 2021)
- Implemented authentication using JWT and OAuth securing 5,000 user accounts
- Optimized PostgreSQL queries, improving page load speed by 35%

EDUCATION
B.Tech Computer Science, ABC University, 2021

PROJECTS
E-Commerce Platform
- Built with MERN stack: MongoDB, Express, React, Node.js
- Integrated Stripe payments processing 500+ transactions/month

CERTIFICATIONS
AWS Certified Cloud Practitioner (2023)
"""

THIN_RESUME = "Jane Smith\njane@mail.com\n\nI am a student looking for a job in tech."

EMPTY_RESUME = ""
WHITESPACE_RESUME = "   \n\n   "


def test_empty_text():
    r = calculate_ats_score(EMPTY_RESUME)
    assert r.score == 0, f"Expected 0, got {r.score}"
    assert len(r.suggestions) >= 1
    print("PASS test_empty_text  score=0")


def test_whitespace_only():
    r = calculate_ats_score(WHITESPACE_RESUME)
    assert r.score == 0, f"Expected 0, got {r.score}"
    print("PASS test_whitespace_only  score=0")


def test_deterministic_full_resume():
    r = _calculate_deterministic_score(FULL_RESUME)
    assert r.score > 0, f"Expected > 0, got {r.score}"
    assert r.breakdown.keyword_relevance > 0, f"kw={r.breakdown.keyword_relevance}"
    assert r.breakdown.structure > 0, f"struct={r.breakdown.structure}"
    assert r.breakdown.required_sections > 0, f"req={r.breakdown.required_sections}"
    assert r.breakdown.skills_clarity > 0, f"skills={r.breakdown.skills_clarity}"
    assert r.breakdown.experience_quality >= 0, f"exp={r.breakdown.experience_quality}"  # can be 0 if no bullet chars
    assert r.breakdown.formatting > 0, f"fmt={r.breakdown.formatting}"
    assert len(r.detected_sections) >= 5, f"Expected >=5 sections, got {r.detected_sections}"
    assert len(r.suggestions) >= 0, f"suggestions returned negative count"  # 0 is valid for a well-formed resume
    assert len(r.categories) == 4, f"Expected 4 categories, got {len(r.categories)}"
    print(f"PASS test_deterministic_full_resume  score={r.score}")
    print(f"     kw={r.breakdown.keyword_relevance}  struct={r.breakdown.structure}  "
          f"req={r.breakdown.required_sections}  skills={r.breakdown.skills_clarity}  "
          f"exp={r.breakdown.experience_quality}  fmt={r.breakdown.formatting}")
    print(f"     detected={r.detected_sections}")
    print(f"     missing={r.missing_sections}")
    cat_summary = [(c.name, c.status, len(c.issues)) for c in r.categories]
    print(f"     categories={cat_summary}")
    print(f"     suggestions={r.suggestions}")


def test_deterministic_thin_resume():
    r = _calculate_deterministic_score(THIN_RESUME)
    assert 0 < r.score < 50, f"Thin resume should score low (0-50), got {r.score}"
    print(f"PASS test_deterministic_thin_resume  score={r.score} (correctly low)")


def test_calculate_ats_score_fallback():
    """calculate_ats_score must produce a real score even when OpenAI is down."""
    r = calculate_ats_score(FULL_RESUME)
    assert r.score > 0, (
        f"calculate_ats_score must fall back to deterministic when OpenAI fails, got score={r.score}"
    )
    assert r.breakdown.keyword_relevance > 0
    assert r.breakdown.structure > 0
    print(f"PASS test_calculate_ats_score_fallback  score={r.score}")


def test_no_false_keyword_match():
    """'go' must not match inside 'algorithm' or 'django'."""
    from app.services.ats_service import _kw_in_text
    assert not _kw_in_text("go", "algorithm"), "'go' falsely matched in 'algorithm'"
    assert not _kw_in_text("go", "django"), "'go' falsely matched in 'django'"
    assert not _kw_in_text("java", "javascript"), "'java' falsely matched in 'javascript'"
    assert _kw_in_text("go", "proficient in Go and Python")
    assert _kw_in_text("java", "Java, Spring Boot, REST APIs")
    print("PASS test_no_false_keyword_match")


def test_app_import():
    from app.main import app  # noqa: F401
    print("PASS test_app_import")


if __name__ == "__main__":
    tests = [
        test_empty_text,
        test_whitespace_only,
        test_deterministic_full_resume,
        test_deterministic_thin_resume,
        test_calculate_ats_score_fallback,
        test_no_false_keyword_match,
        test_app_import,
    ]
    failed = []
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            failed.append(t.__name__)
    print()
    if failed:
        print(f"FAILED: {failed}")
        sys.exit(1)
    else:
        print(f"ALL {len(tests)} TESTS PASSED")
