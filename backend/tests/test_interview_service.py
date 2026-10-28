import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.routers.interview import evaluate_mock_interview_answer, get_interview_session
from app.schemas.interview import MockAnswerRequest
from app.schemas.interview import InterviewQuestionItem
from app.schemas.skill_gap import SkillGapResponse
from app.services import interview_service


def _skill_gap() -> SkillGapResponse:
    return SkillGapResponse(
        target_role="Backend Developer",
        present=["Python", "FastAPI"],
        partial=[],
        missing=["Docker"],
        weak=["System Design"],
        priority_skills=[],
    )


def _profile() -> dict:
    return {
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "projects": [{"name": "Career Platform", "technologies": ["Python", "FastAPI"]}],
    }


def test_profile_based_generator_returns_valid_unique_questions_when_provider_is_unavailable(monkeypatch):
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (None, "not_configured"))

    result = interview_service.generate_interview_questions(
        _profile(), "Backend Developer", _skill_gap(), question_count=14
    )

    assert len(result.questions) == 14
    assert result.generation_mode == "profile_based"
    assert "not configured" in (result.generation_notice or "").lower()
    assert len({interview_service.normalize_question(item.question) for item in result.questions}) == 14
    assert set(interview_service.CATEGORIES).issubset({item.category for item in result.questions})


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


def test_generator_fills_missing_ai_categories_from_profile_candidates(monkeypatch):
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

    assert len(result.questions) == 7
    assert set(interview_service.CATEGORIES) == {item.category for item in result.questions}


def test_provider_configuration_error_is_labeled_without_exposing_details(monkeypatch):
    monkeypatch.setattr(interview_service, "try_structured_ai", lambda **_: (None, "configuration_error"))

    result = interview_service.generate_interview_questions(
        _profile(), "Backend Developer", _skill_gap(), question_count=5
    )

    assert len(result.questions) == 5
    assert "configuration was rejected" in (result.generation_notice or "").lower()


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
    monkeypatch.setattr(interview_service, "evaluate_mock_answer", lambda **_: evaluation)
    request = MockAnswerRequest(
        question=question,
        answer="I would add timeouts, retries, structured logging, and test the failure paths.",
        category="Technical",
        topic="Python",
        target_role="Backend Developer",
        session_id=str(session_id),
    )

    response = evaluate_mock_interview_answer(request, {"id": str(user_id)}, test_db)
    restored = get_interview_session(str(session_id), {"id": str(user_id)}, test_db)

    assert response.score == 82
    assert len(restored.answers) == 1
    assert restored.answers[0]["evaluation"]["score"] == 82
    with pytest.raises(HTTPException) as unauthorized:
        get_interview_session(str(session_id), {"id": str(ObjectId())}, test_db)
    assert unauthorized.value.status_code == 404
