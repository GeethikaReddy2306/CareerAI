from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.interview_question import InterviewQuestion
from app.models.resume import Resume
from app.models.resume_analysis import ResumeAnalysis
from app.models.user import User
from app.schemas.interview import (
    InterviewQuestionItem,
    InterviewQuestionsRequest,
    InterviewQuestionsResponse,
    MockAnswerEvaluation,
    MockAnswerRequest,
)
from app.services import interview_service, skill_gap_service
from app.services.ai_resume_analyzer import analyze_resume_text

router = APIRouter(prefix="/interview/questions", tags=["Interview Prep"])
session_router = APIRouter(prefix="/interview", tags=["Interview Prep"])


@router.post(
    "",
    response_model=InterviewQuestionsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate personalized interview questions",
    description="Generates and stores questions across 7 core categories: Technical, Resume Based, Project Based, Role Specific, Skill Gap Based, Behavioral, and HR.",
)
def create_interview_questions(
    request: InterviewQuestionsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    resume = db.get(Resume, request.resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    if not resume.extracted_text or not resume.extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume contains no extracted text to generate questions.",
        )

    # Ensure ResumeAnalysis exists
    analysis = resume.analysis
    if not analysis:
        ai_result = analyze_resume_text(resume.extracted_text)
        analysis = ResumeAnalysis(
            resume_id=resume.id,
            summary=ai_result.summary,
            skills=ai_result.skills,
            education=[item.model_dump() for item in ai_result.education],
            projects=[item.model_dump() for item in ai_result.projects],
            certifications=ai_result.certifications,
            work_experience=[item.model_dump() for item in ai_result.work_experience],
            strengths=ai_result.strengths,
            weaknesses=ai_result.weaknesses,
            experience_level=ai_result.experience_level,
            suggested_roles=ai_result.suggested_roles,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

    # 1. Compute skill gap to feed into questions
    skill_gap = skill_gap_service.analyze_skill_gaps(
        resume_analysis=analysis,
        target_role=request.target_role,
    )

    # 2. Generate questions
    questions = interview_service.generate_interview_questions(
        resume_analysis=analysis,
        target_role=request.target_role,
        skill_gap=skill_gap,
        job_description=request.job_description,
        question_count=request.question_count,
    )

    # Save to database
    db_objects = [
        InterviewQuestion(
            user_id=current_user.id,
            resume_id=resume.id,
            target_role=request.target_role,
            category=q.category,
            question=q.question,
            difficulty=q.difficulty,
            topic=q.topic,
        )
        for q in questions
    ]
    db.add_all(db_objects)
    db.commit()

    return InterviewQuestionsResponse(questions=questions)


@router.get(
    "",
    response_model=InterviewQuestionsResponse,
    summary="Get saved interview questions",
    description="Retrieves questions previously generated for a candidate resume.",
)
def get_interview_questions(
    resume_id: Annotated[int, Query(description="Resume ID")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    stmt = (
        select(InterviewQuestion)
        .where(
            InterviewQuestion.resume_id == resume_id,
            InterviewQuestion.user_id == current_user.id,
        )
        .order_by(InterviewQuestion.id.asc())
    )
    records = db.scalars(stmt).all()

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interview questions found for this resume.",
        )

    questions = [
        InterviewQuestionItem(
            question=r.question,
            category=r.category,
            difficulty=r.difficulty,
            topic=r.topic,
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
    current_user: Annotated[User, Depends(get_current_user)],
):
    _ = current_user
    result = interview_service.evaluate_mock_answer(
        question=request.question,
        answer=request.answer,
        category=request.category,
        topic=request.topic,
        target_role=request.target_role,
    )
    return MockAnswerEvaluation(
        score=result.score,
        verdict=result.verdict,
        feedback=result.feedback,
        strengths=result.strengths,
        improvements=result.improvements,
    )

