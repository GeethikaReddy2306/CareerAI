from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.routers.router_helpers import ensure_analysis, get_user_resume
from app.schemas.career_readiness import CareerReadinessResponse
from app.services import career_readiness_service, skill_gap_service

router = APIRouter(prefix="/career-readiness", tags=["Career Readiness"])


@router.get(
    "",
    response_model=CareerReadinessResponse,
    summary="Compute candidate career readiness score",
    description="Evaluates career readiness score (0-100) based on skill match (35%), resume quality (20%), project experience (15%), interview readiness (15%), and experience relevance (15%).",
)
def get_career_readiness(
    resume_id: Annotated[str, Query(description="ID of the resume to evaluate")],
    target_role: Annotated[str, Query(min_length=2, description="Target career role, e.g. Backend Developer")],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    resume = get_user_resume(resume_id, current_user["id"], db)

    if not resume.get("extracted_text") or not resume["extracted_text"].strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume contains no extracted text to evaluate.",
        )

    analysis = ensure_analysis(resume, db)

    try:
        skill_gap = skill_gap_service.analyze_skill_gaps(resume_analysis=analysis, target_role=target_role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    readiness = career_readiness_service.calculate_career_readiness(
        resume_analysis=analysis,
        target_role=target_role,
        skill_gap=skill_gap,
    )

    return readiness
