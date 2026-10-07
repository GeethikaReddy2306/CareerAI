from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.career_roadmap import CareerRoadmap
from app.models.resume import Resume
from app.models.resume_analysis import ResumeAnalysis
from app.models.user import User
from app.schemas.career_roadmap import RoadmapCreateRequest, RoadmapPhase, RoadmapResponse
from app.services import roadmap_service, skill_gap_service
from app.services.ai_resume_analyzer import analyze_resume_text

router = APIRouter(prefix="/career/roadmap", tags=["Career Roadmap"])


@router.post(
    "",
    response_model=RoadmapResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate personalized career roadmap",
    description="Generates and stores a personalized multi-phase career roadmap tailored to candidate skill gaps.",
)
def create_career_roadmap(
    request: RoadmapCreateRequest,
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
            detail="Resume contains no extracted text to generate roadmap.",
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

    # 1. Compute skill gap
    skill_gap = skill_gap_service.analyze_skill_gaps(
        resume_analysis=analysis,
        target_role=request.target_role,
    )

    # 2. Generate roadmap
    phases = roadmap_service.generate_career_roadmap(
        resume_analysis=analysis,
        target_role=request.target_role,
        skill_gap=skill_gap,
    )

    phases_data = [p.model_dump() for p in phases]
    current_level = analysis.experience_level or "Junior"

    # Save to database
    roadmap_record = CareerRoadmap(
        user_id=current_user.id,
        resume_id=resume.id,
        target_role=request.target_role,
        current_level=current_level,
        roadmap_data=phases_data,
    )
    db.add(roadmap_record)
    db.commit()
    db.refresh(roadmap_record)

    return RoadmapResponse(
        id=roadmap_record.id,
        resume_id=resume.id,
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

    stmt = select(CareerRoadmap).where(
        CareerRoadmap.resume_id == resume_id,
        CareerRoadmap.user_id == current_user.id,
    ).order_by(CareerRoadmap.created_at.desc())

    roadmap_record = db.scalars(stmt).first()
    if not roadmap_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No roadmap found for this resume.",
        )

    phases = [RoadmapPhase.model_validate(p) for p in roadmap_record.roadmap_data]
    return RoadmapResponse(
        id=roadmap_record.id,
        resume_id=resume.id,
        target_role=roadmap_record.target_role,
        current_level=roadmap_record.current_level,
        roadmap=phases,
    )

