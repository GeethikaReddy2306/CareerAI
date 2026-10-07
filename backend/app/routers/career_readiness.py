from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.resume import Resume
from app.models.resume_analysis import ResumeAnalysis
from app.models.user import User
from app.schemas.career_readiness import CareerReadinessResponse
from app.services import career_readiness_service, skill_gap_service
from app.services.ai_resume_analyzer import analyze_resume_text

router = APIRouter(prefix="/career-readiness", tags=["Career Readiness"])


@router.get(
    "",
    response_model=CareerReadinessResponse,
    summary="Compute candidate career readiness score",
    description="Evaluates career readiness score (0-100) based on skill match (35%), resume quality (20%), project experience (15%), interview readiness (15%), and experience relevance (15%).",
)
def get_career_readiness(
    resume_id: Annotated[int, Query(description="ID of the resume to evaluate")],
    target_role: Annotated[str, Query(min_length=2, description="Target career role, e.g. Backend Developer")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    if not resume.extracted_text or not resume.extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume contains no extracted text to evaluate.",
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

    # 1. Run skill gap analysis
    skill_gap = skill_gap_service.analyze_skill_gaps(
        resume_analysis=analysis,
        target_role=target_role,
    )

    # 2. Compute career readiness score
    readiness = career_readiness_service.calculate_career_readiness(
        resume_analysis=analysis,
        target_role=target_role,
        skill_gap=skill_gap,
    )

    return readiness

