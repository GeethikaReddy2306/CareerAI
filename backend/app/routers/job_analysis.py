from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from app.core.database import get_db
from app.core.db_helpers import to_object_id, utcnow
from app.dependencies.auth import get_current_user
from app.routers.router_helpers import ensure_analysis, get_user_resume
from app.schemas.job_analysis import JobAnalysisRequest, JobAnalysisResponse
from app.services import job_analysis_service

router = APIRouter(prefix="/job-analysis", tags=["Job Analysis"])

_JA = "job_analyses"


@router.post(
    "",
    response_model=JobAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze resume against a job description",
    description="Compares candidate resume profile against target job description requirements, returning match score and skill breakdown.",
)
def create_job_analysis(
    request: JobAnalysisRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    resume = get_user_resume(str(request.resume_id), current_user["id"], db)

    if not resume.get("extracted_text") or not resume["extracted_text"].strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume contains no extracted text to analyze.",
        )

    if not request.job_description or not request.job_description.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description cannot be empty.",
        )

    analysis = ensure_analysis(resume, db)

    try:
        result_data = job_analysis_service.analyze_job_description(
            resume_analysis=analysis, job_description=request.job_description
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    now = utcnow()
    doc = {
        "user_id": to_object_id(current_user["id"]),
        "resume_id": resume["_id"],
        "job_description": request.job_description,
        "match_score": result_data["match_score"],
        "matched_skills": result_data["matched_skills"],
        "partial_skills": result_data["partial_skills"],
        "missing_skills": result_data["missing_skills"],
        "important_keywords": result_data["important_keywords"],
        "interview_topics": result_data["interview_topics"],
        "recommendations": result_data["recommendations"],
        "created_at": now,
        "updated_at": now,
    }
    result = db[_JA].insert_one(doc)

    return JobAnalysisResponse(
        id=str(result.inserted_id),
        resume_id=str(resume["_id"]),
        match_score=result_data["match_score"],
        matched_skills=result_data["matched_skills"],
        partial_skills=result_data["partial_skills"],
        missing_skills=result_data["missing_skills"],
        important_keywords=result_data["important_keywords"],
        interview_topics=result_data["interview_topics"],
        recommendations=result_data["recommendations"],
    )
