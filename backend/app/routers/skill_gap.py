from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.resume import Resume
from app.models.user import User
from app.schemas.skill_gap import SkillGapRequest, SkillGapResponse
from app.services import skill_gap_service
from app.services.ai_resume_analyzer import analyze_resume_text
from app.models.resume_analysis import ResumeAnalysis

router = APIRouter(prefix="/skill-gap", tags=["Skill Gap"])


@router.post(
    "",
    response_model=SkillGapResponse,
    summary="Analyze skill gaps against target role",
    description="Compares candidate skills from resume against target role requirements, categorizing into Strong, Intermediate, Weak, and Missing.",
)
def evaluate_skill_gap(
    request: SkillGapRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    resume = db.get(Resume, request.resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Ensure resume has extracted text
    if not resume.extracted_text or not resume.extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume contains no extracted text to evaluate.",
        )

    # If resume analysis does not yet exist, generate it automatically
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

    result = skill_gap_service.analyze_skill_gaps(
        resume_analysis=analysis,
        target_role=request.target_role,
        target_skills=request.target_skills,
    )
    return result

