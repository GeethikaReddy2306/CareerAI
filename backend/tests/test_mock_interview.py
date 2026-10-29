from app.routers import interview as interview_router
from app.schemas.interview import InterviewQuestionItem
from app.schemas.skill_gap import SkillGapResponse
from app.services import ai_resume_analyzer, interview_service


def _valid_evaluation() -> interview_service.AnswerEvaluationResult:
    return interview_service.AnswerEvaluationResult(
        evaluation=interview_service.AIAnswerEvaluationSchema(
            score=82,
            verdict="Strong",
            feedback="The answer explains a practical design, trade-offs, and how success would be measured.",
            strengths=["Uses concrete operational practices."],
            improvements=["Add a specific production metric."],
            missing_concepts=[],
        ),
        evaluation_mode="ai",
    )


def _skill_gap() -> SkillGapResponse:
    return SkillGapResponse(
        target_role="Backend Developer",
        strong=["Python", "FastAPI"],
        intermediate=["PostgreSQL"],
        weak=[],
        missing=["Docker"],
    )


def _auth_headers(client):
    client.post(
        "/api/auth/register",
        json={"name": "Mock User", "email": "mockuser@example.com", "password": "secret12"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": "mockuser@example.com", "password": "secret12"},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_evaluate_mock_answer_requires_auth(client):
    response = client.post(
        "/api/interview/evaluate",
        json={
            "question": "Explain REST APIs.",
            "answer": "REST is an architectural style using HTTP verbs.",
            "category": "Technical",
            "topic": "REST",
        },
    )
    assert response.status_code in (401, 403)


def test_evaluate_mock_answer_returns_score(client, monkeypatch):
    monkeypatch.setattr(
        interview_router.interview_service,
        "evaluate_mock_answer",
        lambda **_: _valid_evaluation(),
    )
    headers = _auth_headers(client)
    response = client.post(
        "/api/interview/evaluate",
        headers=headers,
        json={
            "question": "How do you design a scalable REST API in FastAPI?",
            "answer": (
                "I would split services by bounded context, use async endpoints, "
                "add connection pooling, cache hot reads in Redis, and measure p95 latency. "
                "For example, in a billing project we reduced timeouts by adding retries and circuit breakers."
            ),
            "category": "Technical",
            "topic": "FastAPI",
            "target_role": "Backend Developer",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["score"] <= 100
    assert body["verdict"] in ("Strong", "Adequate", "Needs Work")
    assert body["feedback"]
    assert body["evaluation_mode"] == "ai"


def test_mock_answer_is_persisted_to_the_owned_session(client, sample_pdf_bytes, monkeypatch):
    # Keep this endpoint integration test deterministic: the AI success is a
    # mocked structured provider response, not a silent local fallback.
    question = InterviewQuestionItem(
        question="How would you design a resilient FastAPI endpoint for a busy service?",
        category="Technical",
        difficulty="Medium",
        topic="FastAPI",
    )
    monkeypatch.setattr(ai_resume_analyzer, "is_openai_configured", lambda: False)
    monkeypatch.setattr(interview_router.skill_gap_service, "analyze_skill_gaps", lambda **_: _skill_gap())
    monkeypatch.setattr(
        interview_router.interview_service,
        "generate_interview_questions",
        lambda **_: interview_service.InterviewGenerationResult(
            questions=[question], generation_mode="ai"
        ),
    )
    monkeypatch.setattr(
        interview_router.interview_service,
        "evaluate_mock_answer",
        lambda **_: _valid_evaluation(),
    )
    headers = _auth_headers(client)
    upload = client.post("/api/resumes/upload", files={"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")}, headers=headers)
    generated = client.post("/api/interview/questions", json={"resume_id": upload.json()["id"], "target_role": "Backend Developer", "question_count": 5}, headers=headers)
    assert generated.status_code == 201
    item = generated.json()["questions"][0]
    evaluation = client.post("/api/interview/evaluate", json={"question": item["question"], "answer": "I would explain the trade-offs, use a concrete example, and measure the result.", "category": item["category"], "topic": item["topic"], "session_id": generated.json()["session_id"]}, headers=headers)
    assert evaluation.status_code == 200
    assert evaluation.json()["evaluation_mode"] == "ai"


def test_demo_mock_interview_persists_a_rule_based_evaluation(client, sample_pdf_bytes, monkeypatch):
    monkeypatch.setattr(interview_service.settings, "INTERVIEW_DEMO_MODE", True)
    monkeypatch.setattr(ai_resume_analyzer, "is_openai_configured", lambda: False)
    headers = _auth_headers(client)
    upload = client.post(
        "/api/resumes/upload",
        files={"file": ("resume.pdf", sample_pdf_bytes, "application/pdf")},
        headers=headers,
    )
    generated = client.post(
        "/api/interview/questions",
        json={"resume_id": upload.json()["id"], "target_role": "Backend Developer", "question_count": 5},
        headers=headers,
    )
    assert generated.status_code == 201
    data = generated.json()
    assert data["generation_mode"] == "demo"
    item = data["questions"][0]

    evaluation = client.post(
        "/api/interview/evaluate",
        json={
            "question": item["question"],
            "answer": "I would define failure modes, add timeouts and logs, test recovery paths, and measure the result.",
            "category": item["category"],
            "topic": item["topic"],
            "session_id": data["session_id"],
        },
        headers=headers,
    )
    assert evaluation.status_code == 200
    assert evaluation.json()["evaluation_mode"] == "demo"
    assert evaluation.json()["evaluation_notice"].startswith("Demo evaluation — rule-based.")

    restored = client.get(f"/api/interview/sessions/{data['session_id']}", headers=headers)
    assert restored.status_code == 200
    assert len(restored.json()["answers"]) == 1
