import os
from pathlib import Path
from typing import Annotated
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.resume import Resume
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.resume import ResumeDetailResponse, ResumeResponse, ResumeUploadResponse
from app.services.resume_parser import extract_text_from_pdf

router = APIRouter(prefix="/resumes", tags=["Resumes"])


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and parse a PDF resume",
    description="Uploads a PDF resume (max 5 MB), saves it securely, extracts its text, and indexes it.",
)
async def upload_resume(
    file: Annotated[UploadFile, File(description="PDF resume document")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File size exceeds the limit of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    # Generate safe unique filename
    unique_filename = f"{uuid.uuid4().hex}.pdf"
    upload_dir = settings.resumes_upload_path
    saved_file_path = upload_dir / unique_filename

    # Save to disk
    with open(saved_file_path, "wb") as buffer:
        buffer.write(contents)

    # Extract text using PyMuPDF
    try:
        extracted_text = extract_text_from_pdf(saved_file_path)
    except Exception:
        # Clean up saved file if extraction fails (ignore Windows lock races)
        if saved_file_path.exists():
            try:
                os.remove(saved_file_path)
            except OSError:
                pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to extract text from PDF. The file may be corrupted or unreadable.",
        )

    # Create Resume record in DB
    resume = Resume(
        user_id=current_user.id,
        original_filename=original_filename,
        file_path=str(saved_file_path),
        file_type="application/pdf",
        file_size=file_size,
        extracted_text=extracted_text,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    return ResumeUploadResponse(
        id=resume.id,
        filename=resume.original_filename,
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
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    stmt = select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.uploaded_at.desc())
    resumes = db.scalars(stmt).all()
    return resumes


@router.get(
    "/{resume_id}",
    response_model=ResumeDetailResponse,
    summary="Get resume details by ID",
    description="Fetches full details including extracted text for a resume owned by the current user.",
)
def get_resume(
    resume_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    return ResumeDetailResponse(
        id=resume.id,
        user_id=resume.user_id,
        original_filename=resume.original_filename,
        file_type=resume.file_type,
        file_size=resume.file_size,
        uploaded_at=resume.uploaded_at,
        updated_at=resume.updated_at,
        extracted_text=resume.extracted_text,
        has_analysis=resume.analysis is not None,
    )


@router.delete(
    "/{resume_id}",
    response_model=APIResponse[dict],
    summary="Delete a resume",
    description="Deletes a resume, its file on disk, and associated analyses.",
)
def delete_resume(
    resume_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Delete physical file
    if resume.file_path and os.path.exists(resume.file_path):
        try:
            os.remove(resume.file_path)
        except OSError:
            pass

    db.delete(resume)
    db.commit()

    return APIResponse(
        success=True,
        message="Resume deleted successfully",
        data={"id": resume_id},
    )
