"""
Shared MongoDB helper utilities for routers.

Provides common patterns used across multiple routers:
- Fetching a resume with ownership check
- Ensuring a ResumeAnalysis document exists (auto-creating via AI if needed)
- Converting analysis documents into a dict compatible with service functions
"""
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.core.db_helpers import to_object_id, utcnow
from app.services import ai_resume_analyzer

_RESUMES = "resumes"
_ANALYSES = "resume_analyses"


def get_user_resume(resume_id: str, user_id: str, db: Database) -> dict[str, Any]:
    """
    Fetch a resume document by string ID and verify the current user owns it.
    Raises HTTP 404 if not found or not owned.
    """
    try:
        oid = to_object_id(resume_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    doc = db[_RESUMES].find_one({"_id": oid})
    if not doc or str(doc["user_id"]) != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return doc


def ensure_analysis(resume_doc: dict[str, Any], db: Database) -> dict[str, Any]:
    """
    Return the existing analysis document for this resume, or create one via AI.
    The returned dict has all fields used by service functions (skills, education, etc.)
    """
    resume_oid: ObjectId = resume_doc["_id"]
    existing = db[_ANALYSES].find_one({"resume_id": resume_oid})
    if existing:
        return existing

    # Run AI analysis to produce the document
    ai_result = ai_resume_analyzer.analyze_resume_text(resume_doc["extracted_text"])
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

