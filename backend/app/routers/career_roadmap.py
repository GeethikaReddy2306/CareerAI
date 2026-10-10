from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database

from app.core.database import get_db
from app.core.db_helpers import to_object_id, utcnow
from app.dependencies.auth import get_current_user
from app.routers.router_helpers import ensure_analysis, get_user_resume
from app.schemas.career_roadmap import RoadmapCreateRequest, RoadmapPhase, RoadmapResponse
from app.services import roadmap_service, skill_gap_service

router = APIRouter(prefix="/career/roadmap", tags=["Career Roadmap"])

_ROADMAPS = "roadmaps"


@router.post(
    "",
    response_model=RoadmapResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate personalized career roadmap",
    description="Generates and stores a personalized multi-phase career roadmap tailored to candidate skill gaps.",
)
def create_career_roadmap(
    request: RoadmapCreateRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    resume = get_user_resume(str(request.resume_id), current_user["id"], db)

    if not resume.get("extracted_text") or not resume["extracted_text"].strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume contains no extracted text to generate roadmap.",
        )

    analysis = ensure_analysis(resume, db)

    skill_gap = skill_gap_service.analyze_skill_gaps(
        resume_analysis=analysis,
        target_role=request.target_role,
    )

    phases = roadmap_service.generate_career_roadmap(
        resume_analysis=analysis,
        target_role=request.target_role,
        skill_gap=skill_gap,
    )

    phases_data = [p.model_dump() for p in phases]
    current_level = analysis.get("experience_level") or "Junior"
    now = utcnow()

    doc = {
        "user_id": to_object_id(current_user["id"]),
        "resume_id": resume["_id"],
        "target_role": request.target_role,
        "current_level": current_level,
        "roadmap_data": phases_data,
        "created_at": now,
        "updated_at": now,
    }
    result = db[_ROADMAPS].insert_one(doc)

    return RoadmapResponse(
        id=str(result.inserted_id),
        resume_id=str(resume["_id"]),
        target_role=request.target_role,
        current_level=current_level,
        roadmap=phases,
    )


@router.get(
    "",
    response_model=RoadmapResponse,
    summary="Get existing career roadmap",
    description="Retrieves the latest generated roadmap for a resume owned by the current user.",
)
def get_career_roadmap(
    resume_id: Annotated[str, Query(description="Resume ID")],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    resume = get_user_resume(resume_id, current_user["id"], db)
    user_oid = to_object_id(current_user["id"])

    roadmap_doc = db[_ROADMAPS].find_one(
        {"resume_id": resume["_id"], "user_id": user_oid},
        sort=[("created_at", -1)],
    )
    if not roadmap_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No roadmap found for this resume.",
        )

    phases = [RoadmapPhase.model_validate(p) for p in roadmap_doc["roadmap_data"]]
    return RoadmapResponse(
        id=str(roadmap_doc["_id"]),
        resume_id=str(resume["_id"]),
        target_role=roadmap_doc["target_role"],
        current_level=roadmap_doc["current_level"],
        roadmap=phases,
    )
