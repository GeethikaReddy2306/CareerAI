from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database

from app.core.database import get_db
from app.core.db_helpers import serialize_doc, to_object_id, utcnow
from app.dependencies.auth import get_current_user
from app.schemas.common import APIResponse
from app.schemas.resume_analysis import (
    ATSScoreResponse,
    ResumeAnalysisDetailResponse,
)
from app.services import ai_resume_analyzer, ats_service
from app.services.llm_resume_review import get_llm_review

router = APIRouter(prefix="/resumes", tags=["Resume Analysis"])

_RESUMES = "resumes"
_ANALYSES = "resume_analyses"


def _get_user_resume(resume_id: str, user_id: str, db: Database) -> dict[str, Any]:
    """Fetch a resume doc and assert ownership. Raises 404 if not found."""
    try:
        oid = to_object_id(resume_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    doc = db[_RESUMES].find_one({"_id": oid})
    if not doc or str(doc["user_id"]) != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return doc


def _get_or_create_analysis(resume_oid: ObjectId, resume_text: str, db: Database) -> dict[str, Any]:
    """Return existing analysis doc, or run AI analysis and create one."""
    existing = db[_ANALYSES].find_one({"resume_id": resume_oid})
    if existing:
        return existing

    ai_result = ai_resume_analyzer.analyze_resume_text(resume_text)
    now = utcnow()
    doc = {
        "resume_id": resume_oid,
        "summary": ai_result.summary,
        "skills": ai_result.skills,
        "education": [item.model_dump() for item in ai_result.education],
        "projects": [item.model_dump() for item in ai_result.projects],
        "certifications": ai_result.certifications,
        "work_experience": [item.model_dump() for item in ai_result.work_experience],
        "strengths": ai_result.strengths,
        "weaknesses": ai_result.weaknesses,
        "experience_level": ai_result.experience_level,
        "suggested_roles": ai_result.suggested_roles,
        "ats_score": None,
        "ats_feedback": None,
        "created_at": now,
        "updated_at": now,
    }
    result = db[_ANALYSES].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def _analysis_doc_to_response(doc: dict[str, Any]) -> ResumeAnalysisDetailResponse:
    """Convert a raw MongoDB analysis document into the Pydantic response model."""
    return ResumeAnalysisDetailResponse(
        id=str(doc["_id"]),
        resume_id=str(doc["resume_id"]),
        summary=doc.get("summary"),
        skills=doc.get("skills"),
        education=doc.get("education"),
        projects=doc.get("projects"),
        certifications=doc.get("certifications"),
        work_experience=doc.get("work_experience"),
        strengths=doc.get("strengths"),
        weaknesses=doc.get("weaknesses"),
        experience_level=doc.get("experience_level"),
        suggested_roles=doc.get("suggested_roles"),
        ats_score=doc.get("ats_score"),
        ats_feedback=doc.get("ats_feedback"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.post(
    "/{resume_id}/analyze",
    response_model=APIResponse[ResumeAnalysisDetailResponse],
    summary="Analyze resume with AI",
    description="Sends extracted resume text to AI, extracts structured career profile, and saves results.",
)
def analyze_resume(
    resume_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
    force_refresh: Annotated[bool, Query(description="Force a new AI analysis even if cached")] = False,
):
    resume = _get_user_resume(resume_id, current_user["id"], db)
    resume_oid = resume["_id"]

    if not resume.get("extracted_text") or not resume["extracted_text"].strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The resume contains no readable extracted text to analyze.",
        )

    existing = db[_ANALYSES].find_one({"resume_id": resume_oid})

    if existing and existing.get("summary") and not force_refresh:
        return APIResponse(
            success=True,
            message="Retrieved existing resume analysis",
            data=_analysis_doc_to_response(existing),
        )

    # Run AI analysis
    ai_result = ai_resume_analyzer.analyze_resume_text(resume["extracted_text"])
    now = utcnow()
    update_fields = {
        "summary": ai_result.summary,
        "skills": ai_result.skills,
        "education": [item.model_dump() for item in ai_result.education],
        "projects": [item.model_dump() for item in ai_result.projects],
        "certifications": ai_result.certifications,
        "work_experience": [item.model_dump() for item in ai_result.work_experience],
        "strengths": ai_result.strengths,
        "weaknesses": ai_result.weaknesses,
        "experience_level": ai_result.experience_level,
        "suggested_roles": ai_result.suggested_roles,
        "updated_at": now,
    }

    if existing:
        db[_ANALYSES].update_one({"_id": existing["_id"]}, {"$set": update_fields})
        updated = db[_ANALYSES].find_one({"_id": existing["_id"]})
    else:
        update_fields["resume_id"] = resume_oid
        update_fields["ats_score"] = None
        update_fields["ats_feedback"] = None
        update_fields["created_at"] = now
        result = db[_ANALYSES].insert_one(update_fields)
        updated = db[_ANALYSES].find_one({"_id": result.inserted_id})

    return APIResponse(
        success=True,
        message="Resume analyzed successfully",
        data=_analysis_doc_to_response(updated),
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
    resume_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    resume = _get_user_resume(resume_id, current_user["id"], db)
    resume_oid = resume["_id"]

    if not resume.get("extracted_text") or not resume["extracted_text"].strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The resume contains no readable extracted text to score.",
        )

    # Deterministic ATS scoring — always runs, never fails due to AI
    ats_result = ats_service.calculate_ats_score(resume["extracted_text"])

    # Optional OpenAI deep-review — never blocks the score
    ai_review = get_llm_review(resume["extracted_text"])
    ats_result = ats_result.model_copy(update={"ai_review": ai_review})

    # Persist ATS results
    now = utcnow()
    ats_data = ats_result.model_dump()
    existing = db[_ANALYSES].find_one({"resume_id": resume_oid})
    if existing:
        db[_ANALYSES].update_one(
            {"_id": existing["_id"]},
            {"$set": {"ats_score": ats_result.score, "ats_feedback": ats_data, "updated_at": now}},
        )
    else:
        db[_ANALYSES].insert_one({
            "resume_id": resume_oid,
            "ats_score": ats_result.score,
            "ats_feedback": ats_data,
            "created_at": now,
            "updated_at": now,
        })

    return ats_result


@router.get(
    "/{resume_id}/analysis",
    response_model=ResumeAnalysisDetailResponse,
    summary="Get saved analysis and ATS report for a resume",
    description="Retrieves the saved AI analysis profile and ATS scoring for the specified resume.",
)
def get_resume_analysis(
    resume_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    resume = _get_user_resume(resume_id, current_user["id"], db)
    analysis = db[_ANALYSES].find_one({"resume_id": resume["_id"]})

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis has been generated for this resume yet.",
        )

    return _analysis_doc_to_response(analysis)
