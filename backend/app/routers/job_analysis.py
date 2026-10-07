from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.job_analysis import JobAnalysis
from app.models.resume import Resume
from app.models.resume_analysis import ResumeAnalysis
from app.models.user import User
from app.schemas.job_analysis import JobAnalysisRequest, JobAnalysisResponse
from app.services import job_analysis_service
from app.services.ai_resume_analyzer import analyze_resume_text

router = APIRouter(prefix="/job-analysis", tags=["Job Analysis"])


@router.post(
    "",
    response_model=JobAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze resume against a job description",
    description="Compares candidate resume profile against target job description requirements, returning match score and skill breakdown.",
)
def create_job_analysis(
    request: JobAnalysisRequest,
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
            detail="Resume contains no extracted text to analyze.",
        )

    if not request.job_description or not request.job_description.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description cannot be empty.",
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

    result_data = job_analysis_service.analyze_job_description(
        resume_analysis=analysis,
        job_description=request.job_description,
    )

    job_analysis = JobAnalysis(
        user_id=current_user.id,
        resume_id=resume.id,
        job_description=request.job_description,
        match_score=result_data["match_score"],
        matched_skills=result_data["matched_skills"],
        partial_skills=result_data["partial_skills"],
        missing_skills=result_data["missing_skills"],
        important_keywords=result_data["important_keywords"],
        interview_topics=result_data["interview_topics"],
        recommendations=result_data["recommendations"],
    )
    db.add(job_analysis)
    db.commit()
    db.refresh(job_analysis)

    return JobAnalysisResponse.model_validate(job_analysis)

