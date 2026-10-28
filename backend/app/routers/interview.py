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

    try:
        skill_gap = skill_gap_service.analyze_skill_gaps(resume_analysis=analysis, target_role=request.target_role)
        user_oid = to_object_id(current_user["id"])
        previous = [row["question"] for row in db[_IQ].find({"user_id": user_oid, "resume_id": resume["_id"], "target_role": request.target_role}, {"question": 1}).sort("created_at", -1).limit(100)]
        questions = interview_service.generate_interview_questions(
            resume_analysis=analysis, target_role=request.target_role, skill_gap=skill_gap,
            job_description=request.job_description, question_count=request.question_count, excluded_questions=previous,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    now = utcnow()
    session_id = request.session_id
    if session_id:
        try:
            session_oid = to_object_id(session_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
        session = db[_SESSIONS].find_one({"_id": session_oid, "user_id": user_oid, "resume_id": resume["_id"]})
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    else:
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

    return InterviewQuestionsResponse(questions=questions, session_id=session_id)


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
    return InterviewQuestionsResponse(questions=questions)


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
    )
    if request.session_id:
        try:
            session_oid = to_object_id(request.session_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
        updated = db[_SESSIONS].update_one(
            {"_id": session_oid, "user_id": user_oid},
            {"$push": {"answers": {"question": request.question, "answer": request.answer, "category": request.category, "topic": request.topic, "evaluation": response.model_dump(), "created_at": utcnow()}}, "$set": {"updated_at": utcnow()}},
        )
        if not updated.matched_count:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    return response
