from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.routers.router_helpers import ensure_analysis, get_user_resume
from app.schemas.skill_gap import SkillGapRequest, SkillGapResponse
from app.services import skill_gap_service

router = APIRouter(prefix="/skill-gap", tags=["Skill Gap"])


@router.post(
    "",
    response_model=SkillGapResponse,
    summary="Analyze skill gaps against target role",
    description="Compares candidate skills from resume against target role requirements, categorizing into Strong, Intermediate, Weak, and Missing.",
)
def evaluate_skill_gap(
    request: SkillGapRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    resume = get_user_resume(str(request.resume_id), current_user["id"], db)

    if not resume.get("extracted_text") or not resume["extracted_text"].strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume contains no extracted text to evaluate.",
        )

    analysis = ensure_analysis(resume, db)

    try:
        result = skill_gap_service.analyze_skill_gaps(
            resume_analysis=analysis, target_role=request.target_role, target_skills=request.target_skills
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return result
