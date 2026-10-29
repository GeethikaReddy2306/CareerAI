from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database

from app.core.database import get_db
from app.core.db_helpers import to_object_id, utcnow
from app.dependencies.auth import get_current_user
from app.routers.router_helpers import ensure_analysis, get_user_resume
from app.schemas.interview import (
    InterviewQuestionItem,
    InterviewQuestionsRequest,
    InterviewQuestionsResponse,
    InterviewSessionResponse,
    MockAnswerEvaluation,
    MockAnswerRequest,
)
from app.services import interview_service, skill_gap_service

router = APIRouter(prefix="/interview/questions", tags=["Interview Prep"])
session_router = APIRouter(prefix="/interview", tags=["Interview Prep"])

_IQ = "interview_questions"
_SESSIONS = "interview_sessions"


def _merge_generation_notices(*notices: Any) -> str | None:
    """Combine server-generated provider notices without discarding the cause."""
    unique: list[str] = []
    for notice in notices:
        text = str(notice or "").strip()
        if text and text not in unique:
            unique.append(text)
    if not unique:
        return None
    # A bounded response keeps an old, unusually large session document from
    # making a normal saved-questions request unwieldy.
    visible = unique[:3]
    suffix = " Additional generation notices are stored with this session." if len(unique) > 3 else ""
    return " ".join(visible) + suffix


def _session_generation_metadata(session: dict[str, Any] | None, generation: Any) -> tuple[str, str | None, str | None]:
    """Return truthful aggregate source metadata when a session receives a batch."""
    if not session:
        return (
            generation.generation_mode,
            generation.generation_notice,
            generation.failure_category,
        )

    previous_mode = str(session.get("generation_mode") or "unknown")
    previous_notice = session.get("generation_notice")
    previous_failure = session.get("failure_category")
    modes = {previous_mode, generation.generation_mode}
    if len(modes) == 1 and "mixed" not in modes:
        return (
            generation.generation_mode,
            generation.generation_notice or previous_notice,
            generation.failure_category or previous_failure,
        )

    failure_values = {str(value) for value in (previous_failure, generation.failure_category) if value}
    failure_category = next(iter(failure_values)) if len(failure_values) == 1 else None
    mixed_notice = (
        "This session contains question batches from more than one generation source. "
        "Questions remain stored with their original source metadata."
    )
    return (
        "mixed",
        _merge_generation_notices(previous_notice, generation.generation_notice, mixed_notice),
        failure_category,
    )


@router.post(
    "",
    response_model=InterviewQuestionsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate personalized interview questions",
    description="Generates and stores questions across 7 core categories: Technical, Resume Based, Project Based, Role Specific, Skill Gap Based, Behavioral, and HR.",
)
def create_interview_questions(
    request: InterviewQuestionsRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    resume = get_user_resume(str(request.resume_id), current_user["id"], db)

    if not resume.get("extracted_text") or not resume["extracted_text"].strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume contains no extracted text to generate questions.",
        )

    analysis = ensure_analysis(resume, db)

    try:
        skill_gap = skill_gap_service.analyze_skill_gaps(
            resume_analysis=analysis, target_role=request.target_role
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    user_oid = to_object_id(current_user["id"])
    session_id = request.session_id
    session: dict[str, Any] | None = None
    if session_id:
        try:
            session_oid = to_object_id(session_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
        session = db[_SESSIONS].find_one({"_id": session_oid, "user_id": user_oid, "resume_id": resume["_id"]})
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
        if session.get("target_role") != request.target_role:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Target role must match the existing interview session")
        existing_jd = str(session.get("job_description") or "").strip()
        requested_jd = str(request.job_description or "").strip()
        if existing_jd and requested_jd and existing_jd != requested_jd:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Job description must match the existing interview session",
            )
        effective_job_description = existing_jd or requested_jd or None
        current_session_questions = session.get("questions", [])
    else:
        session_oid = None
        effective_job_description = request.job_description
        current_session_questions = []

    # Keep historic questions as exclusions as well as the current session's
    # questions, so a later practice run cannot quietly repeat prior prompts.
    previous = list(
        db[_IQ].find(
            {"user_id": user_oid, "resume_id": resume["_id"], "target_role": request.target_role,
             **({"session_id": {"$ne": session_oid}} if session_oid else {})},
            {"question": 1, "category": 1},
        ).sort("created_at", -1).limit(50)
    )
    generation = interview_service.generate_interview_questions(
        resume_analysis=analysis,
        target_role=request.target_role,
        skill_gap=skill_gap,
        job_description=effective_job_description,
        question_count=request.question_count,
        excluded_questions=current_session_questions,
        previous_questions=previous,
    )
    if not generation.questions:
        detail = generation.generation_notice or "No valid interview questions could be generated from the supplied profile."
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

    now = utcnow()
    questions = generation.questions
    session_mode, session_notice, session_failure = _session_generation_metadata(session, generation)
    if session_oid is None:
        session_oid = db[_SESSIONS].insert_one({
            "user_id": user_oid, "resume_id": resume["_id"], "target_role": request.target_role,
            "job_description": effective_job_description,
            "generation_mode": session_mode,
            "generation_notice": session_notice,
            "failure_category": session_failure,
            "created_at": now, "updated_at": now, "questions": [], "answers": [],
        }).inserted_id
        session_id = str(session_oid)
    db_docs = [
        {
            "user_id": user_oid,
            "resume_id": resume["_id"],
            "target_role": request.target_role,
            "category": q.category,
            "question": q.question,
            "difficulty": q.difficulty,
            "topic": q.topic,
            "session_id": session_oid,
            "generation_mode": generation.generation_mode,
            "generation_notice": generation.generation_notice,
            "failure_category": generation.failure_category,
            "created_at": now,
        }
        for q in questions
    ]
    if db_docs:
        db[_IQ].insert_many(db_docs)
        db[_SESSIONS].update_one(
            {"_id": session_oid, "user_id": user_oid},
            {
                "$push": {"questions": {"$each": [q.model_dump() for q in questions]}},
                "$set": {
                    "updated_at": now,
                    "job_description": effective_job_description,
                    "generation_mode": session_mode,
                    "generation_notice": session_notice,
                    "failure_category": session_failure,
                },
            },
        )

    return InterviewQuestionsResponse(
        questions=questions,
        session_id=session_id,
        requested_count=request.question_count,
        returned_count=len(questions),
        generation_mode=generation.generation_mode,
        generation_notice=generation.generation_notice,
        failure_category=generation.failure_category,
    )


@router.get(
    "",
    response_model=InterviewQuestionsResponse,
    summary="Get saved interview questions",
    description="Retrieves questions previously generated for a candidate resume.",
)
def get_interview_questions(
    resume_id: Annotated[str, Query(description="Resume ID")],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
    target_role: Annotated[str | None, Query(description="Optional target-role filter")] = None,
    session_id: Annotated[str | None, Query(description="Optional interview-session filter")] = None,
):
    resume = get_user_resume(resume_id, current_user["id"], db)
    user_oid = to_object_id(current_user["id"])

    filters: dict[str, Any] = {"resume_id": resume["_id"], "user_id": user_oid}
    if target_role:
        filters["target_role"] = target_role
    if session_id:
        try:
            filters["session_id"] = to_object_id(session_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    records = list(db[_IQ].find(filters).sort("_id", 1))

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interview questions found for this resume.",
        )

    questions = [
        InterviewQuestionItem(
            question=r["question"],
            category=r["category"],
            difficulty=r["difficulty"],
            topic=r["topic"],
        )
        for r in records
    ]
    modes = {record.get("generation_mode", "unknown") for record in records}
    failure_categories = {record.get("failure_category") for record in records if record.get("failure_category")}
    record_session_ids = {str(record["session_id"]) for record in records if record.get("session_id")}
    saved_notice = _merge_generation_notices(*(record.get("generation_notice") for record in records))
    return InterviewQuestionsResponse(
        questions=questions,
        session_id=next(iter(record_session_ids)) if len(record_session_ids) == 1 else None,
        requested_count=len(questions),
        returned_count=len(questions),
        generation_mode=next(iter(modes)) if len(modes) == 1 else "mixed",
        generation_notice=(
            saved_notice
            or (
                "Saved profile-based questions are shown because the AI provider was unavailable at generation time."
                if modes == {"profile_based"}
                else None
            )
        ),
        failure_category=next(iter(failure_categories)) if len(failure_categories) == 1 else None,
    )


@session_router.get(
    "/sessions/{session_id}",
    response_model=InterviewSessionResponse,
    summary="Restore a saved mock interview session",
)
def get_interview_session(
    session_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    try:
        session_oid = to_object_id(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    session = db[_SESSIONS].find_one({"_id": session_oid, "user_id": to_object_id(current_user["id"])})
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    return InterviewSessionResponse(
        id=str(session["_id"]),
        resume_id=str(session["resume_id"]),
        target_role=session["target_role"],
        job_description=session.get("job_description"),
        questions=[InterviewQuestionItem.model_validate(question) for question in session.get("questions", [])],
        answers=session.get("answers", []),
        generation_mode=session.get("generation_mode", "unknown"),
        generation_notice=session.get("generation_notice"),
        failure_category=session.get("failure_category"),
    )


@session_router.post(
    "/evaluate",
    response_model=MockAnswerEvaluation,
    summary="Evaluate a mock interview answer",
    description="Scores a candidate's mock interview answer and returns coach-style feedback.",
)
def evaluate_mock_interview_answer(
    request: MockAnswerRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    user_oid = to_object_id(current_user["id"])
    session_oid = None
    effective_category = request.category
    effective_topic = request.topic
    effective_target_role = request.target_role
    if request.session_id:
        try:
            session_oid = to_object_id(request.session_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
        session = db[_SESSIONS].find_one({"_id": session_oid, "user_id": user_oid})
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
        session_question = next(
            (question for question in session.get("questions", []) if question.get("question") == request.question),
            None,
        )
        if not session_question:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Question does not belong to this interview session")
        if any(answer.get("question") == request.question for answer in session.get("answers", [])):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This question has already been evaluated for the session")
        # The client chooses the question, but a persisted session is the
        # authoritative source for its category, topic, and target role.
        effective_category = str(session_question.get("category") or request.category)
        effective_topic = str(session_question.get("topic") or request.topic)
        effective_target_role = str(session.get("target_role") or request.target_role or "") or None

    evaluation_result = interview_service.evaluate_mock_answer(
        question=request.question,
        answer=request.answer,
        category=effective_category,
        topic=effective_topic,
        target_role=effective_target_role,
    )
    if evaluation_result.evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=evaluation_result.evaluation_notice or "AI answer evaluation failed. The answer was not saved.",
        )
    result = evaluation_result.evaluation
    response = MockAnswerEvaluation(
        score=result.score,
        verdict=result.verdict,
        feedback=result.feedback,
        strengths=result.strengths,
        improvements=result.improvements,
        missing_concepts=result.missing_concepts,
        evaluation_mode=evaluation_result.evaluation_mode,
        evaluation_notice=evaluation_result.evaluation_notice,
        failure_category=evaluation_result.failure_category,
    )
    if session_oid:
        updated = db[_SESSIONS].update_one(
            {"_id": session_oid, "user_id": user_oid},
            {"$push": {"answers": {"question": request.question, "answer": request.answer, "category": effective_category, "topic": effective_topic, "evaluation": response.model_dump(), "created_at": utcnow()}}, "$set": {"updated_at": utcnow()}},
        )
        if not updated.matched_count:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    return response
