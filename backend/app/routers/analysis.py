from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.resume import Resume
from app.models.resume_analysis import ResumeAnalysis
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.resume_analysis import (
    ATSScoreResponse,
    ResumeAnalysisDetailResponse,
)
from app.services import ai_resume_analyzer, ats_service
from app.services.llm_resume_review import get_llm_review

router = APIRouter(prefix="/resumes", tags=["Resume Analysis"])


def _get_user_resume(resume_id: int, user_id: int, db: Session) -> Resume:
    """Helper to fetch a resume and assert ownership."""
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )
    return resume


@router.post(
    "/{resume_id}/analyze",
    response_model=APIResponse[ResumeAnalysisDetailResponse],
    summary="Analyze resume with AI",
    description="Sends extracted resume text to AI, extracts structured career profile, and saves results.",
)
def analyze_resume(
    resume_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    force_refresh: Annotated[bool, Query(description="Force a new AI analysis even if cached")] = False,
):
    resume = _get_user_resume(resume_id, current_user.id, db)

    if not resume.extracted_text or not resume.extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The resume contains no readable extracted text to analyze.",
        )

    # Check for existing analysis to avoid unnecessary repeated AI calls
    existing_analysis = resume.analysis
    if existing_analysis and existing_analysis.summary and not force_refresh:
        return APIResponse(
            success=True,
            message="Retrieved existing resume analysis",
            data=ResumeAnalysisDetailResponse.model_validate(existing_analysis),
        )

    # Perform AI resume analysis
    ai_result = ai_resume_analyzer.analyze_resume_text(resume.extracted_text)

    # Convert Pydantic submodels to dicts for JSON storage
    education_data = [item.model_dump() for item in ai_result.education]
    projects_data = [item.model_dump() for item in ai_result.projects]
    work_exp_data = [item.model_dump() for item in ai_result.work_experience]

    if existing_analysis:
        existing_analysis.summary = ai_result.summary
        existing_analysis.skills = ai_result.skills
        existing_analysis.education = education_data
        existing_analysis.projects = projects_data
        existing_analysis.certifications = ai_result.certifications
        existing_analysis.work_experience = work_exp_data
        existing_analysis.strengths = ai_result.strengths
        existing_analysis.weaknesses = ai_result.weaknesses
        existing_analysis.experience_level = ai_result.experience_level
        existing_analysis.suggested_roles = ai_result.suggested_roles
        analysis_record = existing_analysis
    else:
        analysis_record = ResumeAnalysis(
            resume_id=resume.id,
            summary=ai_result.summary,
            skills=ai_result.skills,
            education=education_data,
            projects=projects_data,
            certifications=ai_result.certifications,
            work_experience=work_exp_data,
            strengths=ai_result.strengths,
            weaknesses=ai_result.weaknesses,
            experience_level=ai_result.experience_level,
            suggested_roles=ai_result.suggested_roles,
        )
        db.add(analysis_record)

    db.commit()
    db.refresh(analysis_record)

    return APIResponse(
        success=True,
        message="Resume analyzed successfully",
        data=ResumeAnalysisDetailResponse.model_validate(analysis_record),
    )


@router.post(
    "/{resume_id}/ats-score",
    response_model=ATSScoreResponse,
    tags=["ATS"],
    summary="Generate ATS compatibility score and feedback",
    description=(
        "Evaluates resume text with AI-powered ATS scoring, itemized per-line feedback, "
        "and an optional OpenAI-powered deep review — all returned in a single response (0-100)."
    ),
)
def compute_ats_score(
    resume_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    resume = _get_user_resume(resume_id, current_user.id, db)

    if not resume.extracted_text or not resume.extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The resume contains no readable extracted text to score.",
        )

    # Deterministic/AI score first — this must always return.
    ats_result = ats_service.calculate_ats_score(resume.extracted_text)

    # Optional Anthropic deep-review; never raises, never blocks the score above.
    ai_review = get_llm_review(resume.extracted_text)
    ats_result = ats_result.model_copy(update={"ai_review": ai_review})

    # Persist ATS results into resume_analyses.
    existing_analysis = resume.analysis
    if existing_analysis:
        existing_analysis.ats_score = ats_result.score
        existing_analysis.ats_feedback = ats_result.model_dump()
    else:
        existing_analysis = ResumeAnalysis(
            resume_id=resume.id,
            ats_score=ats_result.score,
            ats_feedback=ats_result.model_dump(),
        )
        db.add(existing_analysis)

    db.commit()
    db.refresh(existing_analysis)

    return ats_result


@router.get(
    "/{resume_id}/analysis",
    response_model=ResumeAnalysisDetailResponse,
    summary="Get saved analysis and ATS report for a resume",
    description="Retrieves the saved AI analysis profile and ATS scoring for the specified resume.",
)
def get_resume_analysis(
    resume_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    resume = _get_user_resume(resume_id, current_user.id, db)

    if not resume.analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis has been generated for this resume yet.",
        )

    return ResumeAnalysisDetailResponse.model_validate(resume.analysis)
