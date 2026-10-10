import os
from pathlib import Path
from typing import Annotated, Any
import uuid

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pymongo.database import Database

from app.core.config import settings
from app.core.database import get_db
from app.core.db_helpers import serialize_doc, to_object_id, utcnow
from app.dependencies.auth import get_current_user
from app.schemas.common import APIResponse
from app.schemas.resume import ResumeDetailResponse, ResumeResponse, ResumeUploadResponse
from app.services.resume_parser import extract_text_from_pdf

router = APIRouter(prefix="/resumes", tags=["Resumes"])

_COL = "resumes"
_ANALYSIS_COL = "resume_analyses"


def _get_user_resume_doc(resume_id: str, user_id: str, db: Database) -> dict[str, Any]:
    """Fetch a resume document and verify ownership. Raises 404 if not found/not owned."""
    try:
        oid = to_object_id(resume_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    doc = db[_COL].find_one({"_id": oid})
    if not doc or str(doc["user_id"]) != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return doc


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and parse a PDF resume",
    description="Uploads a PDF resume (max 5 MB), saves it securely, extracts its text, and indexes it.",
)
async def upload_resume(
    file: Annotated[UploadFile, File(description="PDF resume document")],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    # Validate file extension
    original_filename = file.filename or "resume.pdf"
    file_ext = Path(original_filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension: '{file_ext}'. Only PDF files are accepted.",
        )

    # Validate MIME type
    if file.content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file content type: '{file.content_type}'. Only 'application/pdf' is accepted.",
        )

    # Read content and validate file size
    contents = await file.read()
    file_size = len(contents)

    if file_size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")

    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File size exceeds the limit of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    # Generate safe unique filename and save to disk
    unique_filename = f"{uuid.uuid4().hex}.pdf"
    upload_dir = settings.resumes_upload_path
    saved_file_path = upload_dir / unique_filename

    with open(saved_file_path, "wb") as buffer:
        buffer.write(contents)

    # Extract text using PyMuPDF
    try:
        extracted_text = extract_text_from_pdf(saved_file_path)
    except Exception:
        if saved_file_path.exists():
            try:
                os.remove(saved_file_path)
            except OSError:
                pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to extract text from PDF. The file may be corrupted or unreadable.",
        )

    now = utcnow()
    user_oid = to_object_id(current_user["id"])
    doc = {
        "user_id": user_oid,
        "original_filename": original_filename,
        "file_path": str(saved_file_path),
        "file_type": "application/pdf",
        "file_size": file_size,
        "extracted_text": extracted_text,
        "uploaded_at": now,
        "updated_at": now,
    }
    result = db[_COL].insert_one(doc)

    return ResumeUploadResponse(
        id=str(result.inserted_id),
        filename=original_filename,
        message="Resume uploaded and parsed successfully",
        text_length=len(extracted_text) if extracted_text else 0,
    )


@router.get(
    "",
    response_model=list[ResumeResponse],
    summary="List all resumes for current user",
    description="Returns metadata for all resumes uploaded by the authenticated user.",
)
def list_resumes(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    user_oid = to_object_id(current_user["id"])
    docs = list(db[_COL].find({"user_id": user_oid}).sort("uploaded_at", -1))
    result = []
    for doc in docs:
        result.append(ResumeResponse(
            id=str(doc["_id"]),
            user_id=str(doc["user_id"]),
            original_filename=doc["original_filename"],
            file_type=doc["file_type"],
            file_size=doc["file_size"],
            uploaded_at=doc["uploaded_at"],
            updated_at=doc["updated_at"],
        ))
    return result


@router.get(
    "/{resume_id}",
    response_model=ResumeDetailResponse,
    summary="Get resume details by ID",
    description="Fetches full details including extracted text for a resume owned by the current user.",
)
def get_resume(
    resume_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    doc = _get_user_resume_doc(resume_id, current_user["id"], db)
    # Check if analysis exists
    analysis_exists = db[_ANALYSIS_COL].find_one({"resume_id": doc["_id"]}) is not None
    return ResumeDetailResponse(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        original_filename=doc["original_filename"],
        file_type=doc["file_type"],
        file_size=doc["file_size"],
        uploaded_at=doc["uploaded_at"],
        updated_at=doc["updated_at"],
        extracted_text=doc.get("extracted_text"),
        has_analysis=analysis_exists,
    )


@router.delete(
    "/{resume_id}",
    response_model=APIResponse[dict],
    summary="Delete a resume",
    description="Deletes a resume, its file on disk, and associated analyses.",
)
def delete_resume(
    resume_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Database, Depends(get_db)],
):
    doc = _get_user_resume_doc(resume_id, current_user["id"], db)
    oid = doc["_id"]

    # Delete physical file
    file_path = doc.get("file_path")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    # Delete related analysis documents
    db[_ANALYSIS_COL].delete_one({"resume_id": oid})
    # Delete the resume itself
    db[_COL].delete_one({"_id": oid})

    return APIResponse(
        success=True,
        message="Resume deleted successfully",
        data={"id": resume_id},
    )
