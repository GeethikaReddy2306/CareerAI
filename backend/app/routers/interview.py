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

    skill_gap = skill_gap_service.analyze_skill_gaps(resume_analysis=analysis, target_role=request.target_role)
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
        current_session_questions = session.get("questions", [])
    else:
        session_oid = None
        current_session_questions = []

    # Previous sessions are a preference, rather than an absolute constraint.
    # A session's own questions remain strict exclusions so it cannot repeat itself.
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
        job_description=request.job_description,
        question_count=request.question_count,
        excluded_questions=current_session_questions,
        previous_questions=previous,
    )
    if not generation.questions:
        detail = generation.generation_notice or "No valid interview questions could be generated from the supplied profile."
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

    now = utcnow()
    questions = generation.questions
    if session_oid is None:
        session_oid = db[_SESSIONS].insert_one({
            "user_id": user_oid, "resume_id": resume["_id"], "target_role": request.target_role,
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
            "created_at": now,
        }
        for q in questions
    ]
    if db_docs:
        db[_IQ].insert_many(db_docs)
        db[_SESSIONS].update_one({"_id": session_oid}, {"$push": {"questions": {"$each": [q.model_dump() for q in questions]}}, "$set": {"updated_at": now}})

    return InterviewQuestionsResponse(
        questions=questions,
        session_id=session_id,
        requested_count=request.question_count,
        returned_count=len(questions),
        generation_mode=generation.generation_mode,
        generation_notice=generation.generation_notice,
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
):
    resume = get_user_resume(resume_id, current_user["id"], db)
    user_oid = to_object_id(current_user["id"])

    records = list(
        db[_IQ].find(
            {"resume_id": resume["_id"], "user_id": user_oid}
        ).sort("_id", 1)
    )

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
    return InterviewQuestionsResponse(
        questions=questions,
        requested_count=len(questions),
        returned_count=len(questions),
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
        questions=[InterviewQuestionItem.model_validate(question) for question in session.get("questions", [])],
        answers=session.get("answers", []),
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
    if request.session_id:
        try:
            session_oid = to_object_id(request.session_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
        session = db[_SESSIONS].find_one({"_id": session_oid, "user_id": user_oid})
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
        if request.question not in {question.get("question") for question in session.get("questions", [])}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Question does not belong to this interview session")
        if any(answer.get("question") == request.question for answer in session.get("answers", [])):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This question has already been evaluated for the session")

    result = interview_service.evaluate_mock_answer(
        question=request.question,
        answer=request.answer,
        category=request.category,
        topic=request.topic,
        target_role=request.target_role,
    )
    response = MockAnswerEvaluation(
        score=result.score,
        verdict=result.verdict,
        feedback=result.feedback,
        strengths=result.strengths,
        improvements=result.improvements,
        missing_concepts=result.missing_concepts,
    )
    if session_oid:
        updated = db[_SESSIONS].update_one(
            {"_id": session_oid, "user_id": user_oid},
            {"$push": {"answers": {"question": request.question, "answer": request.answer, "category": request.category, "topic": request.topic, "evaluation": response.model_dump(), "created_at": utcnow()}}, "$set": {"updated_at": utcnow()}},
        )
        if not updated.matched_count:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    return response
