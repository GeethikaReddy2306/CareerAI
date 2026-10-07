"""One-off live API test runner against the already-running server. Not part of pytest."""
from __future__ import annotations

import json
import io
import sqlite3
import time
import traceback
from pathlib import Path

import httpx
import pymupdf

BASE = "http://127.0.0.1:8001"
DB = Path("career_intelligence.db")
results: list[dict] = []
stamp = str(int(time.time()))


def rec(name: str, method: str, status: str, detail: str = ""):
    results.append({"api": name, "method": method, "status": status, "detail": detail})
    print(f"[{status}] {method:6} {name}: {detail}")


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 60), text, fontsize=10)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


BACKEND_RESUME = """Priya Sharma
priya.sharma@example.com | github.com/priya | linkedin.com/in/priya

PROFESSIONAL SUMMARY
Backend engineer with 4 years building REST APIs in Python and FastAPI with PostgreSQL.

SKILLS
Python, FastAPI, SQL, REST APIs, Git, Docker, PostgreSQL, Redis

WORK EXPERIENCE
Backend Developer - NovaSoft (2021 - Present)
- Designed FastAPI services and SQL schemas.
- Built REST APIs consumed by web and mobile clients.

PROJECTS
Job Matcher API (Python, FastAPI, PostgreSQL)
- REST service matching resumes to job descriptions.

EDUCATION
B.Tech Computer Science, 2020

CERTIFICATIONS
AWS Cloud Practitioner
"""

WEAK_RESUME = """Alex Newbie
alex@example.com

Student looking for internships. Knows HTML and some Java.

EDUCATION
High School, 2024
"""

JD = """We are looking for a Backend Developer with experience in Python,
FastAPI, PostgreSQL, REST APIs, Docker and AWS.

Requirements:
- Strong Python knowledge
- FastAPI or Django
- PostgreSQL
- REST API development
- Docker
- AWS
- Git
- Basic system design knowledge
"""


def leak_check(resp: httpx.Response) -> str | None:
    body = resp.text.lower()
    needles = [
        "traceback",
        "secret_key",
        "openai_api_key",
        "sk-proj-",
        "cloudinary_api_secret",
        "password_hash",
        "postgresql+psycopg://",
        "d:\\\\minor project",
        "site-packages",
    ]
    for n in needles:
        if n in body:
            return n
    return None


def main():
    client = httpx.Client(base_url=BASE, timeout=60.0)

    # Health / docs
    r = client.get("/")
    rec("Root health", "GET", "PASS" if r.status_code == 200 and r.json().get("success") else "FAIL", f"{r.status_code} {r.text[:120]}")
    r = client.get("/health")
    rec("GET /health (not implemented)", "GET", "PASS" if r.status_code == 404 else "FAIL", f"{r.status_code}")
    r = client.get("/docs")
    rec("OpenAPI docs", "GET", "PASS" if r.status_code == 200 else "FAIL", f"{r.status_code}")
    r = client.get("/openapi.json")
    paths = sorted((r.json().get("paths") or {}).keys()) if r.status_code == 200 else []
    rec("OpenAPI paths", "GET", "PASS" if paths else "FAIL", ", ".join(paths))

    # Auth validation
    email_a = f"apitest.a.{stamp}@example.com"
    email_b = f"apitest.b.{stamp}@example.com"

    r = client.post("/api/auth/register", json={"name": "API Test User", "email": email_a, "password": "Test@12345"})
    rec("Register", "POST", "PASS" if r.status_code == 201 else "FAIL", f"{r.status_code} {r.text[:180]}")
    user_a_id = r.json().get("data", {}).get("id") if r.status_code == 201 else None

    r = client.post("/api/auth/register", json={"name": "API Test User", "email": email_a, "password": "Test@12345"})
    rec("Register duplicate email", "POST", "PASS" if r.status_code == 400 else "FAIL", f"{r.status_code} {r.text[:180]}")

    r = client.post("/api/auth/register", json={"name": "X", "email": "not-an-email", "password": "Test@12345"})
    rec("Register invalid email", "POST", "PASS" if r.status_code == 422 else "FAIL", f"{r.status_code}")

    r = client.post("/api/auth/register", json={"name": "X", "email": f"weak.{stamp}@example.com", "password": "123"})
    rec("Register weak password (<6)", "POST", "PASS" if r.status_code == 422 else "FAIL", f"{r.status_code} {r.text[:120]}")

    r = client.post("/api/auth/register", json={"email": f"miss.{stamp}@example.com", "password": "Test@12345"})
    rec("Register missing name", "POST", "PASS" if r.status_code == 422 else "FAIL", f"{r.status_code}")

    r = client.post("/api/auth/login", json={"email": email_a, "password": "Test@12345"})
    rec("Login", "POST", "PASS" if r.status_code == 200 and r.json().get("access_token") else "FAIL", f"{r.status_code}")
    token_a = r.json().get("access_token") if r.status_code == 200 else ""
    headers_a = {"Authorization": f"Bearer {token_a}"}

    r = client.post("/api/auth/login", json={"email": email_a, "password": "WrongPass1"})
    rec("Login invalid password", "POST", "PASS" if r.status_code == 401 else "FAIL", f"{r.status_code}")

    r = client.post("/api/auth/login", json={"email": f"nouser.{stamp}@example.com", "password": "Test@12345"})
    rec("Login nonexistent user", "POST", "PASS" if r.status_code == 401 else "FAIL", f"{r.status_code}")

    r = client.get("/api/auth/me", headers=headers_a)
    ok = r.status_code == 200 and r.json().get("email") == email_a
    rec("Me", "GET", "PASS" if ok else "FAIL", f"{r.status_code} {r.text[:160]}")

    r = client.get("/api/auth/me")
    rec("Me missing token", "GET", "PASS" if r.status_code in (401, 403) else "FAIL", f"{r.status_code}")
    leak = leak_check(r)
    rec("Missing token leak check", "GET", "FAIL" if leak else "PASS", leak or "no secrets")

    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    rec("Me invalid token", "GET", "PASS" if r.status_code == 401 else "FAIL", f"{r.status_code} {r.text[:160]}")
    leak = leak_check(r)
    rec("Invalid token leak check", "GET", "FAIL" if leak else "PASS", leak or "no secrets")

    # User B
    r = client.post("/api/auth/register", json={"name": "User B", "email": email_b, "password": "Test@12345"})
    rec("Register User B", "POST", "PASS" if r.status_code == 201 else "FAIL", f"{r.status_code}")
    r = client.post("/api/auth/login", json={"email": email_b, "password": "Test@12345"})
    token_b = r.json().get("access_token") if r.status_code == 200 else ""
    headers_b = {"Authorization": f"Bearer {token_b}"}

    pdf = make_pdf(BACKEND_RESUME)
    r = client.post("/api/resumes/upload", headers=headers_a, files={"file": ("resume.pdf", pdf, "application/pdf")})
    rec("Resume Upload", "POST", "PASS" if r.status_code == 201 and r.json().get("text_length", 0) > 50 else "FAIL", f"{r.status_code} {r.text[:200]}")
    resume_id = r.json().get("id") if r.status_code == 201 else None

    r = client.post("/api/resumes/upload", headers=headers_a, files={"file": ("resume.txt", b"hello", "application/pdf")})
    rec("Upload invalid extension", "POST", "PASS" if r.status_code == 400 else "FAIL", f"{r.status_code}")

    r = client.post("/api/resumes/upload", headers=headers_a, files={"file": ("resume.pdf", pdf, "text/plain")})
    rec("Upload invalid MIME", "POST", "PASS" if r.status_code == 400 else "FAIL", f"{r.status_code}")

    r = client.post("/api/resumes/upload", headers=headers_a, files={"file": ("resume.pdf", b"0" * (6 * 1024 * 1024), "application/pdf")})
    rec("Upload oversized", "POST", "PASS" if r.status_code == 413 else "FAIL", f"{r.status_code}")

    empty_pdf = make_pdf("")
    r = client.post("/api/resumes/upload", headers=headers_a, files={"file": ("empty.pdf", empty_pdf, "application/pdf")})
    rec("Upload empty-ish PDF", "POST", "PASS" if r.status_code in (201, 400) else "FAIL", f"{r.status_code} {r.text[:160]}")
    empty_id = r.json().get("id") if r.status_code == 201 else None

    r = client.post("/api/resumes/upload", headers=headers_a, files={"file": ("bad.pdf", b"%PDF-1.4 not a real pdf %%%%", "application/pdf")})
    rec("Upload corrupted PDF", "POST", "PASS" if r.status_code == 400 else "FAIL", f"{r.status_code} {r.text[:180]}")
    leak = leak_check(r)
    rec("Corrupted PDF leak check", "POST", "FAIL" if leak else "PASS", leak or "no secrets")

    r = client.get("/api/resumes", headers=headers_a)
    rec("List resumes User A", "GET", "PASS" if r.status_code == 200 else "FAIL", f"{r.status_code} count={len(r.json()) if r.status_code==200 else None}")

    r = client.get("/api/resumes", headers=headers_b)
    b_list = r.json() if r.status_code == 200 else []
    rec("List isolation User B empty/other", "GET", "PASS" if r.status_code == 200 and resume_id not in [x.get("id") for x in b_list] else "FAIL", f"{r.status_code} {b_list}")

    # Parse check
    r = client.get(f"/api/resumes/{resume_id}", headers=headers_a)
    text = (r.json().get("extracted_text") or "") if r.status_code == 200 else ""
    needed = ["Priya", "Python", "FastAPI", "B.Tech", "Job Matcher", "AWS"]
    rec("Resume parsing content", "GET", "PASS" if all(k.lower() in text.lower() for k in ["python", "fastapi", "education", "skills"]) else "FAIL", f"len={len(text)} has={[k for k in needed if k.lower() in text.lower()]}")

    # IDOR
    idor_endpoints = [
        ("GET", f"/api/resumes/{resume_id}", None),
        ("POST", f"/api/resumes/{resume_id}/analyze", None),
        ("POST", f"/api/resumes/{resume_id}/ats-score", None),
        ("GET", f"/api/resumes/{resume_id}/analysis", None),
        ("POST", "/api/job-analysis", {"resume_id": resume_id, "job_description": JD}),
        ("POST", "/api/skill-gap", {"resume_id": resume_id, "target_role": "Backend Developer"}),
        ("GET", f"/api/career-readiness?resume_id={resume_id}&target_role=Backend%20Developer", None),
        ("POST", "/api/career/roadmap", {"resume_id": resume_id, "target_role": "Backend Developer"}),
        ("POST", "/api/interview/questions", {"resume_id": resume_id, "target_role": "Backend Developer", "question_count": 5}),
    ]
    idor_ok = True
    idor_details = []
    for method, url, body in idor_endpoints:
        if method == "GET":
            resp = client.get(url, headers=headers_b)
        else:
            resp = client.post(url, headers=headers_b, json=body)
        ok_status = resp.status_code in (401, 403, 404)
        if not ok_status:
            idor_ok = False
        idor_details.append(f"{method} {url} -> {resp.status_code}")
        leak = leak_check(resp)
        if leak:
            idor_ok = False
            idor_details.append(f"LEAK {leak}")
    rec("IDOR ownership (User B vs User A resume)", "MIX", "PASS" if idor_ok else "FAIL", "; ".join(idor_details))

    # Analyze
    r = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers_a)
    data = r.json() if r.status_code == 200 else {}
    payload = data.get("data") or {}
    keys_ok = all(k in payload for k in ["skills", "education", "projects", "work_experience", "strengths", "weaknesses"]) if payload else False
    rec("Resume Analysis", "POST", "PASS" if r.status_code == 200 and keys_ok else "FAIL", f"{r.status_code} skills={payload.get('skills')} strengths={payload.get('strengths')}")

    r = client.post("/api/resumes/999999/analyze", headers=headers_a)
    rec("Analyze invalid resume ID", "POST", "PASS" if r.status_code == 404 else "FAIL", f"{r.status_code}")

    r = client.post(f"/api/resumes/{resume_id}/analyze")
    rec("Analyze missing auth", "POST", "PASS" if r.status_code in (401, 403) else "FAIL", f"{r.status_code}")

    if empty_id:
        r = client.post(f"/api/resumes/{empty_id}/analyze", headers=headers_a)
        rec("Analyze empty PDF text", "POST", "PASS" if r.status_code == 400 else "FAIL", f"{r.status_code} {r.text[:160]}")

    # ATS
    r = client.post(f"/api/resumes/{resume_id}/ats-score", headers=headers_a)
    ats = r.json() if r.status_code == 200 else {}
    score = ats.get("score")
    rec(
        "ATS Score",
        "POST",
        "PASS" if r.status_code == 200 and isinstance(score, int) and 0 <= score <= 100 and ats.get("breakdown") and ats.get("suggestions") is not None else "FAIL",
        f"{r.status_code} {json.dumps(ats)[:300]}",
    )
    r = client.post("/api/resumes/999999/ats-score", headers=headers_a)
    rec("ATS invalid resume", "POST", "PASS" if r.status_code == 404 else "FAIL", f"{r.status_code}")
    r = client.post(f"/api/resumes/{resume_id}/ats-score")
    rec("ATS missing auth", "POST", "PASS" if r.status_code in (401, 403) else "FAIL", f"{r.status_code}")

    # Job analysis
    r = client.post("/api/job-analysis", headers=headers_a, json={"resume_id": resume_id, "job_description": JD})
    ja = r.json() if r.status_code == 201 else {}
    fields = ["match_score", "matched_skills", "partial_skills", "missing_skills", "important_keywords", "interview_topics", "recommendations"]
    rec(
        "Resume + JD",
        "POST",
        "PASS" if r.status_code == 201 and all(k in ja for k in fields) and 0 <= ja.get("match_score", -1) <= 100 else "FAIL",
        f"{r.status_code} score={ja.get('match_score')} matched={ja.get('matched_skills')} missing={ja.get('missing_skills')}",
    )
    r = client.post("/api/job-analysis", headers=headers_a, json={"resume_id": resume_id, "job_description": ""})
    rec("JD empty", "POST", "PASS" if r.status_code in (400, 422) else "FAIL", f"{r.status_code}")
    r = client.post("/api/job-analysis", headers=headers_a, json={"resume_id": resume_id, "job_description": "short"})
    rec("JD extremely short", "POST", "PASS" if r.status_code in (400, 422) else "FAIL", f"{r.status_code}")
    r = client.post("/api/job-analysis", headers=headers_a, json={"resume_id": 999999, "job_description": JD})
    rec("JD invalid resume", "POST", "PASS" if r.status_code == 404 else "FAIL", f"{r.status_code}")
    r = client.post("/api/job-analysis", json={"resume_id": resume_id, "job_description": JD})
    rec("JD missing auth", "POST", "PASS" if r.status_code in (401, 403) else "FAIL", f"{r.status_code}")

    # Skill gap
    r = client.post("/api/skill-gap", headers=headers_a, json={"resume_id": resume_id, "target_role": "Backend Developer"})
    sg = r.json() if r.status_code == 200 else {}
    rec(
        "Skill Gap",
        "POST",
        "PASS" if r.status_code == 200 and all(k in sg for k in ["strong", "intermediate", "weak", "missing", "prioritized_skills"]) else "FAIL",
        f"{r.status_code} strong={sg.get('strong')} missing={sg.get('missing')} prio={sg.get('prioritized_skills')}",
    )
    overlap = set(sg.get("strong") or []) & set(sg.get("missing") or [])
    rec("Skill gap strong/missing disjoint", "POST", "PASS" if not overlap else "FAIL", f"overlap={overlap}")
    r = client.post("/api/skill-gap", headers=headers_a, json={"resume_id": resume_id, "target_role": "Quantum Blockchain Unicorn Wrangler"})
    rec("Skill gap unknown role", "POST", "PASS" if r.status_code == 200 else "FAIL", f"{r.status_code} {r.text[:200]}")
    r = client.post("/api/skill-gap", headers=headers_a, json={"resume_id": resume_id, "target_role": ""})
    rec("Skill gap empty role", "POST", "PASS" if r.status_code in (400, 422) else "FAIL", f"{r.status_code}")
    r = client.post("/api/skill-gap", headers=headers_a, json={"resume_id": 999999, "target_role": "Backend Developer"})
    rec("Skill gap invalid resume", "POST", "PASS" if r.status_code == 404 else "FAIL", f"{r.status_code}")
    r = client.post("/api/skill-gap", json={"resume_id": resume_id, "target_role": "Backend Developer"})
    rec("Skill gap missing auth", "POST", "PASS" if r.status_code in (401, 403) else "FAIL", f"{r.status_code}")

    # Career readiness
    r = client.get("/api/career-readiness", headers=headers_a, params={"resume_id": resume_id, "target_role": "Backend Developer"})
    cr = r.json() if r.status_code == 200 else {}
    bd = cr.get("breakdown") or {}
    bd_ok = bd and all(0 <= float(v) <= 100 for v in bd.values())
    rec(
        "Career Readiness",
        "GET",
        "PASS" if r.status_code == 200 and 0 <= cr.get("overall_score", -1) <= 100 and bd_ok and cr.get("strengths") and cr.get("areas_to_improve") and cr.get("recommendations") else "FAIL",
        f"{r.status_code} score={cr.get('overall_score')} breakdown={bd}",
    )
    score_a = cr.get("overall_score")

    weak_pdf = make_pdf(WEAK_RESUME)
    r = client.post("/api/resumes/upload", headers=headers_a, files={"file": ("weak.pdf", weak_pdf, "application/pdf")})
    weak_id = r.json().get("id") if r.status_code == 201 else None
    if weak_id:
        r = client.get("/api/career-readiness", headers=headers_a, params={"resume_id": weak_id, "target_role": "Backend Developer"})
        score_w = r.json().get("overall_score") if r.status_code == 200 else None
        rec("Readiness scores not identical across profiles", "GET", "PASS" if score_w is not None and score_w != score_a else "FAIL", f"backend={score_a} weak={score_w}")
    r = client.get("/api/career-readiness", headers=headers_a, params={"resume_id": 999999, "target_role": "Backend Developer"})
    rec("Readiness invalid resume", "GET", "PASS" if r.status_code == 404 else "FAIL", f"{r.status_code}")
    r = client.get("/api/career-readiness", headers=headers_a, params={"resume_id": resume_id})
    rec("Readiness missing target role", "GET", "PASS" if r.status_code == 422 else "FAIL", f"{r.status_code}")
    r = client.get("/api/career-readiness", params={"resume_id": resume_id, "target_role": "Backend Developer"})
    rec("Readiness missing auth", "GET", "PASS" if r.status_code in (401, 403) else "FAIL", f"{r.status_code}")

    # Roadmap
    r = client.post("/api/career/roadmap", headers=headers_a, json={"resume_id": resume_id, "target_role": "Backend Developer"})
    rm = r.json() if r.status_code == 201 else {}
    phases = rm.get("roadmap") or []
    phase_fields_ok = all(all(k in p for k in ["phase", "title", "description", "skills", "topics", "projects", "estimated_weeks", "priority"]) for p in phases) if phases else False
    blob = json.dumps(rm).lower()
    wasted_basics = ("learn python basics" in blob) or ("learn sql basics" in blob)
    rec(
        "Roadmap",
        "POST",
        "PASS" if r.status_code == 201 and rm.get("target_role") and rm.get("current_level") and phases and phase_fields_ok and not wasted_basics else "FAIL",
        f"{r.status_code} level={rm.get('current_level')} phases={len(phases)} wasted_basics={wasted_basics} titles={[p.get('title') for p in phases]}",
    )
    r = client.post("/api/career/roadmap", headers=headers_a, json={"resume_id": 999999, "target_role": "Backend Developer"})
    rec("Roadmap invalid resume", "POST", "PASS" if r.status_code == 404 else "FAIL", f"{r.status_code}")
    r = client.post("/api/career/roadmap", headers=headers_a, json={"resume_id": resume_id, "target_role": ""})
    rec("Roadmap missing target role", "POST", "PASS" if r.status_code in (400, 422) else "FAIL", f"{r.status_code}")
    r = client.post("/api/career/roadmap", json={"resume_id": resume_id, "target_role": "Backend Developer"})
    rec("Roadmap missing auth", "POST", "PASS" if r.status_code in (401, 403) else "FAIL", f"{r.status_code}")

    # Interview
    r = client.post("/api/interview/questions", headers=headers_a, json={"resume_id": resume_id, "target_role": "Backend Developer", "question_count": 15})
    iq = r.json() if r.status_code == 201 else {}
    qs = iq.get("questions") or []
    cats = {q.get("category") for q in qs}
    expected_cats = {"Technical", "Resume Based", "Project Based", "Role Specific", "Skill Gap Based", "Behavioral", "HR"}
    related = any("fastapi" in (q.get("question") or "").lower() or "fastapi" in (q.get("topic") or "").lower() or "python" in (q.get("question") or "").lower() for q in qs)
    rec(
        "Interview Questions",
        "POST",
        "PASS" if r.status_code == 201 and len(qs) == 15 and expected_cats.issubset(cats) and related else "FAIL",
        f"{r.status_code} count={len(qs)} cats={sorted(cats)} related={related} sample={qs[:2]}",
    )
    r = client.post("/api/interview/questions", headers=headers_a, json={"resume_id": resume_id, "target_role": "Backend Developer", "question_count": 5})
    rec("Interview count=5", "POST", "PASS" if r.status_code == 201 and len(r.json().get("questions", [])) == 5 else "FAIL", f"{r.status_code} {r.text[:120]}")
    r = client.post("/api/interview/questions", headers=headers_a, json={"resume_id": resume_id, "target_role": "Backend Developer", "question_count": 2})
    rec("Interview invalid count=2", "POST", "PASS" if r.status_code == 422 else "FAIL", f"{r.status_code}")
    r = client.post("/api/interview/questions", headers=headers_a, json={"resume_id": resume_id, "target_role": "Backend Developer", "question_count": 999})
    rec("Interview very large count", "POST", "PASS" if r.status_code == 422 else "FAIL", f"{r.status_code}")
    r = client.post("/api/interview/questions", headers=headers_a, json={"resume_id": 999999, "target_role": "Backend Developer", "question_count": 5})
    rec("Interview invalid resume", "POST", "PASS" if r.status_code == 404 else "FAIL", f"{r.status_code}")
    r = client.post("/api/interview/questions", json={"resume_id": resume_id, "target_role": "Backend Developer", "question_count": 5})
    rec("Interview missing auth", "POST", "PASS" if r.status_code in (401, 403) else "FAIL", f"{r.status_code}")

    # 500 should not leak
    r = client.get("/api/resumes/not-an-int", headers=headers_a)
    rec("Invalid path param type", "GET", "PASS" if r.status_code == 422 else "FAIL", f"{r.status_code}")
    leak = leak_check(r)
    rec("422 leak check", "GET", "FAIL" if leak else "PASS", leak or "no secrets")

    # DB inspection
    if DB.exists():
        con = sqlite3.connect(DB)
        cur = con.cursor()
        tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        rec("SQLite tables present", "DB", "PASS" if {"users", "resumes", "job_analyses", "roadmaps", "interview_questions"}.issubset(tables) else "FAIL", str(sorted(tables)))
        alembic = list(cur.execute("SELECT name FROM sqlite_master WHERE name='alembic_version'"))
        rec("Alembic version table", "DB", "PASS" if alembic else "FAIL", str(alembic))
        if alembic:
            rec("Alembic revision", "DB", "PASS", str(list(cur.execute("SELECT * FROM alembic_version"))))
        if user_a_id and resume_id:
            row = cur.execute("SELECT id, user_id, file_path, extracted_text IS NOT NULL FROM resumes WHERE id=?", (resume_id,)).fetchone()
            rec("Resume row user_id", "DB", "PASS" if row and row[1] == user_a_id else "FAIL", str(row))
            cloudinary = "cloudinary.com" in str(row[2]).lower() if row else False
            rec("Cloudinary URL stored", "DB", "FAIL" if not cloudinary else "PASS", f"file_path={row[2] if row else None}")
            ja_row = cur.execute("SELECT user_id, resume_id, created_at, updated_at FROM job_analyses WHERE resume_id=? ORDER BY id DESC LIMIT 1", (resume_id,)).fetchone()
            rec("job_analyses row", "DB", "PASS" if ja_row and ja_row[0] == user_a_id and ja_row[1] == resume_id else "FAIL", str(ja_row))
            rm_row = cur.execute("SELECT user_id, resume_id, created_at, updated_at FROM roadmaps WHERE resume_id=? ORDER BY id DESC LIMIT 1", (resume_id,)).fetchone()
            rec("roadmaps row", "DB", "PASS" if rm_row and rm_row[0] == user_a_id else "FAIL", str(rm_row))
            iq_row = cur.execute("SELECT COUNT(*), MIN(user_id), MIN(resume_id) FROM interview_questions WHERE resume_id=?", (resume_id,)).fetchone()
            rec("interview_questions rows", "DB", "PASS" if iq_row and iq_row[0] > 0 and iq_row[1] == user_a_id else "FAIL", str(iq_row))
        con.close()
    else:
        rec("SQLite file exists", "DB", "FAIL", "career_intelligence.db missing")

    # Summary
    passed = sum(1 for x in results if x["status"] == "PASS")
    failed = sum(1 for x in results if x["status"] == "FAIL")
    print("\n=== SUMMARY ===")
    print(f"Total={len(results)} Passed={passed} Failed={failed}")
    for x in results:
        if x["status"] == "FAIL":
            print("FAIL", x)

    Path("_live_backend_results.json").write_text(json.dumps({"results": results, "passed": passed, "failed": failed}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
