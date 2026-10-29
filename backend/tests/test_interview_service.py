import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.routers import interview as interview_router
from app.routers.interview import (
    create_interview_questions,
    evaluate_mock_interview_answer,
    get_interview_questions,
    get_interview_session,
)
from app.schemas.interview import InterviewQuestionItem, InterviewQuestionsRequest, MockAnswerRequest
from app.schemas.skill_gap import SkillGapResponse
from app.services import interview_service


@pytest.fixture(autouse=True)
def _disable_runtime_demo_mode(monkeypatch):
    """Keep unit tests explicit about whether they exercise demo mode."""
    monkeypatch.setattr(interview_service.settings, "INTERVIEW_DEMO_MODE", False)


def _skill_gap() -> SkillGapResponse:
    return SkillGapResponse(
        target_role="Backend Developer",
        strong=["Python", "FastAPI"],
        intermediate=["PostgreSQL"],
        missing=["Docker"],
        weak=["System Design"],
        prioritized_skills=[],
    )


def _profile() -> dict:
    return {
        "skills": ["Python", "FastAPI", "PostgreSQL", "TypeScript"],
        "projects": [{"name": "Career Platform", "technologies": ["Python", "FastAPI"]}],
        "experience_level": "Mid-level",
    }


def _question(text: str, category: str = "Technical", topic: str = "Python") -> InterviewQuestionItem:
    return InterviewQuestionItem(
        question=text,
        category=category,
        difficulty="Medium",
        topic=topic,
    )


def _insert_resume_with_analysis(test_db, user_id: ObjectId) -> ObjectId:
    resume_id = ObjectId()
    test_db["resumes"].insert_one(
        {
            "_id": resume_id,
            "user_id": user_id,
            "extracted_text": "Python and FastAPI backend experience.",
        }
    )
    test_db["resume_analyses"].insert_one({"resume_id": resume_id, **_profile()})
    return resume_id


def test_profile_based_generator_returns_valid_unique_questions_in_explicit_offline_mode(monkeypatch):
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (None, "not_configured"))
    monkeypatch.setattr(interview_service.settings, "INTERVIEW_PROFILE_FALLBACK_ENABLED", True)

    result = interview_service.generate_interview_questions(
        _profile(), "Backend Developer", _skill_gap(), question_count=14
    )

    assert len(result.questions) == 14
    assert result.generation_mode == "profile_based"
    assert "not configured" in (result.generation_notice or "").lower()
    assert len({interview_service.normalize_question(item.question) for item in result.questions}) == 14
    assert set(interview_service.CATEGORIES).issubset({item.category for item in result.questions})
    technical_questions = [item.question for item in result.questions if item.category == "Technical"]
    assert all("TypeScript" not in question for question in technical_questions)


def test_explicit_demo_mode_skips_the_provider_and_labels_questions(monkeypatch):
    def provider_must_not_run(**_kwargs):
        raise AssertionError("demo mode must not call OpenAI")

    monkeypatch.setattr(interview_service.settings, "INTERVIEW_DEMO_MODE", True)
    monkeypatch.setattr(interview_service, "try_structured_ai", provider_must_not_run)

    result = interview_service.generate_interview_questions(
        _profile(), "Backend Developer", _skill_gap(), question_count=7
    )

    assert len(result.questions) == 7
    assert result.generation_mode == "demo"
    assert (result.generation_notice or "").startswith("Demo mode — not AI-generated.")
    assert all("TypeScript" not in item.question for item in result.questions if item.category == "Technical")


def test_generator_returns_smaller_valid_set_instead_of_raising(monkeypatch):
    candidates = [
        InterviewQuestionItem(question="How would you design a Python API?", category="Technical", difficulty="Medium", topic="Python"),
        InterviewQuestionItem(question="How would you design a Python API?", category="Technical", difficulty="Medium", topic="Python"),
        InterviewQuestionItem(question="Tell me about a project trade-off.", category="Behavioral", difficulty="Medium", topic="Collaboration"),
    ]
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (None, "provider_error"))
    monkeypatch.setattr(
        interview_service,
        "_heuristic_interview_questions",
        lambda *args, **kwargs: interview_service.AIInterviewQuestionsSchema(questions=candidates),
    )

    result = interview_service.generate_interview_questions(
        _profile(), "Backend Developer", _skill_gap(), question_count=5
    )

    assert len(result.questions) == 2
    assert result.generation_mode == "profile_based"
    assert "unavailable" in (result.generation_notice or "").lower()


def test_duplicate_detection_is_category_aware():
    existing = [
        InterviewQuestionItem(
            question="Describe a project trade-off you made.",
            category="Behavioral",
            difficulty="Medium",
            topic="Collaboration",
        )
    ]
    assert not interview_service.is_duplicate_question(
        "Describe a project trade-off in your system design.", existing, category="Technical"
    )
    assert interview_service.is_duplicate_question(
        "Describe a project trade-off you made.", existing, category="Technical"
    )


def test_ai_questions_are_not_blended_with_profile_fallback(monkeypatch):
    technical_only = interview_service.AIInterviewQuestionsSchema(
        questions=[
            InterviewQuestionItem(
                question=f"How would you approach Python API concern {index}?",
                category="Technical",
                difficulty="Medium",
                topic="Python",
            )
            for index in range(20)
        ]
    )
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (technical_only, "success"))

    result = interview_service.generate_interview_questions(
        _profile(), "Backend Developer", _skill_gap(), question_count=7
    )

    # Number-only variations are near duplicates, so the service returns the
    # one valid question instead of padding with profile fallback templates.
    assert len(result.questions) == 1
    assert {item.category for item in result.questions} == {"Technical"}
    assert result.generation_mode == "ai"


def test_large_question_request_asks_the_provider_for_enough_candidates(monkeypatch):
    prompts: list[str] = []

    def empty_response(**kwargs):
        prompts.append(kwargs["prompt"])
        return interview_service.AIInterviewQuestionsSchema(questions=[]), "success"

    monkeypatch.setattr(interview_service, "try_structured_ai", empty_response)

    result = interview_service.generate_interview_questions(
        _profile(), "Backend Developer", _skill_gap(), question_count=50
    )

    assert "Generate 60 candidate interview questions" in prompts[0]
    assert result.generation_mode == "error"
    assert result.failure_category == "invalid_output"


def test_unrelated_project_evidence_is_not_sent_for_backend_question_generation(monkeypatch):
    prompts: list[str] = []
    profile = {
        "skills": ["Python", "FastAPI", "TypeScript", "React"],
        "projects": [
            {"name": "Backend API", "technologies": ["Python", "FastAPI"]},
            {"name": "Frontend Console", "technologies": ["TypeScript", "React"]},
        ],
    }

    def empty_response(**kwargs):
        prompts.append(kwargs["prompt"])
        return interview_service.AIInterviewQuestionsSchema(questions=[]), "success"

    monkeypatch.setattr(interview_service, "try_structured_ai", empty_response)
    interview_service.generate_interview_questions(profile, "Backend Developer", _skill_gap(), question_count=5)

    assert "Backend API" in prompts[0]
    assert "Frontend Console" not in prompts[0]
    assert "TypeScript" not in prompts[0]


def test_previous_session_questions_are_not_reused_to_pad_a_generation(monkeypatch):
    repeated = _question("How would you make a Python API resilient under production load?")
    response = interview_service.AIInterviewQuestionsSchema(questions=[repeated])
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (response, "success"))

    result = interview_service.generate_interview_questions(
        _profile(),
        "Backend Developer",
        _skill_gap(),
        question_count=5,
        previous_questions=[repeated],
    )

    assert result.questions == []
    assert result.generation_mode == "ai"
    assert "0 validated unique" in (result.generation_notice or "")


def test_provider_configuration_error_is_labeled_without_exposing_details(monkeypatch):
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (None, "configuration_error"))

    result = interview_service.generate_interview_questions(
        _profile(), "Backend Developer", _skill_gap(), question_count=5
    )

    assert result.questions == []
    assert result.generation_mode == "error"
    assert result.failure_category == "configuration_error"
    assert "authentication failed" in (result.generation_notice or "").lower()


def test_unsupported_model_is_reported_without_fallback(monkeypatch):
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (None, "model_unavailable"))

    result = interview_service.generate_interview_questions(
        _profile(), "Backend Developer", _skill_gap(), question_count=5
    )

    assert result.questions == []
    assert result.failure_category == "model_unavailable"
    assert "model is unavailable" in (result.generation_notice or "").lower()


def test_timeout_uses_clearly_labelled_profile_fallback(monkeypatch):
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (None, "timeout"))

    result = interview_service.generate_interview_questions(
        _profile(), "Backend Developer", _skill_gap(), question_count=5
    )

    assert len(result.questions) == 5
    assert result.generation_mode == "profile_based"
    assert result.failure_category == "timeout"


def test_invalid_ai_question_output_is_not_saved_as_success(monkeypatch):
    malformed = interview_service.AIInterviewQuestionsSchema(
        questions=[
            InterviewQuestionItem(
                question="Too short",
                category="Technical",
                difficulty="Medium",
                topic="Python",
            )
        ]
    )
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (malformed, "success"))

    result = interview_service.generate_interview_questions(
        _profile(), "Backend Developer", _skill_gap(), question_count=5
    )

    assert result.questions == []
    assert result.generation_mode == "error"
    assert result.failure_category == "invalid_output"


def test_rejected_evaluation_does_not_use_a_hidden_fallback(monkeypatch):
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (None, "configuration_error"))

    result = interview_service.evaluate_mock_answer(
        question="How would you make a Python API resilient?",
        answer="I would identify failure modes, add timeouts and retries, and verify the recovery path.",
        category="Technical",
        topic="Python",
        target_role="Backend Developer",
    )

    assert result.evaluation is None
    assert result.evaluation_mode == "error"
    assert result.failure_category == "configuration_error"


def test_valid_ai_evaluation_is_returned_as_ai(monkeypatch):
    evaluation = interview_service.AIAnswerEvaluationSchema(
        score=84,
        verdict="Strong",
        feedback="The answer clearly explains trade-offs, recovery behavior, and verification steps.",
        strengths=["Explained operational trade-offs."],
        improvements=["Add a concrete project metric."],
        missing_concepts=[],
    )
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (evaluation, "success"))

    result = interview_service.evaluate_mock_answer(
        question="How would you make a Python API resilient?",
        answer="I would add timeouts, retries, logs, and monitor recovery behavior in production.",
        category="Technical",
        topic="Python",
        target_role="Backend Developer",
    )

    assert result.evaluation is evaluation
    assert result.evaluation_mode == "ai"


def test_explicit_demo_mode_returns_rule_based_evaluation_without_provider(monkeypatch):
    def provider_must_not_run(**_kwargs):
        raise AssertionError("demo mode must not call OpenAI")

    monkeypatch.setattr(interview_service.settings, "INTERVIEW_DEMO_MODE", True)
    monkeypatch.setattr(interview_service, "try_structured_ai", provider_must_not_run)

    result = interview_service.evaluate_mock_answer(
        question="How would you make a Python API resilient?",
        answer="I would use timeouts, retries, logging, tests, and a project example to explain the trade-offs.",
        category="Technical",
        topic="Python",
        target_role="Backend Developer",
    )

    assert result.evaluation is not None
    assert result.evaluation_mode == "demo"
    assert (result.evaluation_notice or "").startswith("Demo evaluation — rule-based.")


def test_mock_answer_is_scoped_persisted_and_restorable(test_db, monkeypatch):
    user_id = ObjectId()
    resume_id = ObjectId()
    session_id = ObjectId()
    question = "How would you make a Python API resilient?"
    test_db["interview_sessions"].insert_one({
        "_id": session_id,
        "user_id": user_id,
        "resume_id": resume_id,
        "target_role": "Backend Developer",
        "questions": [{"question": question, "category": "Technical", "difficulty": "Medium", "topic": "Python"}],
        "answers": [],
    })
    evaluation = interview_service.AIAnswerEvaluationSchema(
        score=82,
        verdict="Strong",
        feedback="Clear and relevant answer.",
        strengths=["Explained the approach."],
        improvements=[],
        missing_concepts=[],
    )
    captured: dict = {}

    def evaluate(**kwargs):
        captured.update(kwargs)
        return interview_service.AnswerEvaluationResult(evaluation=evaluation, evaluation_mode="ai")

    monkeypatch.setattr(interview_service, "evaluate_mock_answer", evaluate)
    request = MockAnswerRequest(
        question=question,
        answer="I would add timeouts, retries, structured logging, and test the failure paths.",
        category="HR",
        topic="Untrusted caller topic",
        target_role="Untrusted caller role",
        session_id=str(session_id),
    )

    response = evaluate_mock_interview_answer(request, {"id": str(user_id)}, test_db)
    restored = get_interview_session(str(session_id), {"id": str(user_id)}, test_db)

    assert response.score == 82
    assert response.evaluation_mode == "ai"
    assert len(restored.answers) == 1
    assert restored.answers[0]["evaluation"]["score"] == 82
    assert restored.answers[0]["category"] == "Technical"
    assert restored.answers[0]["topic"] == "Python"
    assert captured["category"] == "Technical"
    assert captured["topic"] == "Python"
    assert captured["target_role"] == "Backend Developer"
    with pytest.raises(HTTPException) as unauthorized:
        get_interview_session(str(session_id), {"id": str(ObjectId())}, test_db)
    assert unauthorized.value.status_code == 404


def test_rejected_evaluation_is_not_persisted(test_db, monkeypatch):
    user_id = ObjectId()
    session_id = ObjectId()
    question = "How would you make a Python API resilient?"
    test_db["interview_sessions"].insert_one({
        "_id": session_id,
        "user_id": user_id,
        "resume_id": ObjectId(),
        "target_role": "Backend Developer",
        "questions": [{"question": question, "category": "Technical", "difficulty": "Medium", "topic": "Python"}],
        "answers": [],
    })
    monkeypatch.setattr(
        interview_service,
        "evaluate_mock_answer",
        lambda **_: interview_service.AnswerEvaluationResult(
            evaluation=None,
            evaluation_mode="error",
            evaluation_notice="OpenAI authentication failed.",
            failure_category="configuration_error",
        ),
    )
    request = MockAnswerRequest(
        question=question,
        answer="I would use timeouts, retries, logging, and a tested recovery path.",
        session_id=str(session_id),
    )

    with pytest.raises(HTTPException) as error:
        evaluate_mock_interview_answer(request, {"id": str(user_id)}, test_db)

    assert error.value.status_code == 503
    assert test_db["interview_sessions"].find_one({"_id": session_id})["answers"] == []


def test_failed_generation_does_not_create_a_session(test_db, monkeypatch):
    user_id = ObjectId()
    resume_id = _insert_resume_with_analysis(test_db, user_id)
    monkeypatch.setattr(interview_router.skill_gap_service, "analyze_skill_gaps", lambda **_: _skill_gap())
    monkeypatch.setattr(
        interview_router.interview_service,
        "generate_interview_questions",
        lambda **_: interview_service.InterviewGenerationResult(
            questions=[],
            generation_mode="error",
            generation_notice="OpenAI authentication failed.",
            failure_category="configuration_error",
        ),
    )

    with pytest.raises(HTTPException) as error:
        create_interview_questions(
            InterviewQuestionsRequest(resume_id=str(resume_id), target_role="Backend Developer", question_count=5),
            {"id": str(user_id)},
            test_db,
        )

    assert error.value.status_code == 503
    assert test_db["interview_sessions"].count_documents({}) == 0
    assert test_db["interview_questions"].count_documents({}) == 0


def test_session_keeps_mixed_source_metadata_and_saved_notice(test_db, monkeypatch):
    user_id = ObjectId()
    resume_id = _insert_resume_with_analysis(test_db, user_id)
    batches = [
        interview_service.InterviewGenerationResult(
            questions=[_question("How would you design a Python API for reliable background jobs?")],
            generation_mode="profile_based",
            generation_notice="AI question generation timed out; a clearly labelled profile-based result was used instead.",
            failure_category="timeout",
        ),
        interview_service.InterviewGenerationResult(
            questions=[_question("How would you trace latency through a FastAPI service and its database?")],
            generation_mode="ai",
        ),
    ]
    monkeypatch.setattr(interview_router.skill_gap_service, "analyze_skill_gaps", lambda **_: _skill_gap())
    monkeypatch.setattr(
        interview_router.interview_service,
        "generate_interview_questions",
        lambda **_: batches.pop(0),
    )

    first = create_interview_questions(
        InterviewQuestionsRequest(resume_id=str(resume_id), target_role="Backend Developer", question_count=5),
        {"id": str(user_id)},
        test_db,
    )
    second = create_interview_questions(
        InterviewQuestionsRequest(
            resume_id=str(resume_id),
            target_role="Backend Developer",
            question_count=5,
            session_id=first.session_id,
        ),
        {"id": str(user_id)},
        test_db,
    )
    restored = get_interview_session(first.session_id, {"id": str(user_id)}, test_db)
    saved = get_interview_questions(
        str(resume_id),
        {"id": str(user_id)},
        test_db,
        target_role="Backend Developer",
        session_id=first.session_id,
    )

    assert second.generation_mode == "ai"
    assert restored.generation_mode == "mixed"
    assert "more than one generation source" in (restored.generation_notice or "")
    assert saved.generation_mode == "mixed"
    assert "timed out" in (saved.generation_notice or "")
    stored_modes = [item["generation_mode"] for item in test_db["interview_questions"].find({"session_id": ObjectId(first.session_id)})]
    assert stored_modes == ["profile_based", "ai"]
