from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import (
    auth_router,
    resume_router,
    analysis_router,
    job_analysis_router,
    skill_gap_router,
    career_readiness_router,
    career_roadmap_router,
    interview_router,
    interview_session_router,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("career_platform")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure upload directories exist
    settings.resumes_upload_path.mkdir(parents=True, exist_ok=True)
    logger.info("Application startup: verified storage directories.")
    yield
    # Shutdown
    logger.info("Application shutdown.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Backend API for AI-Powered Career Intelligence, Preparation & Upskilling Platform.\n\n"
        "Implemented Features:\n"
        "- Secure User Authentication (JWT + Bcrypt)\n"
        "- PDF Resume Upload & Parsing (PyMuPDF)\n"
        "- AI-Powered Structured Resume Analysis (OpenAI)\n"
        "- Transparent Deterministic ATS Compatibility Scoring (0-100)\n"
        "- Resume + Job Description Matching & Scoring\n"
        "- Comprehensive Skill Gap Analysis with Normalization\n"
        "- Multi-Factor Career Readiness Scoring\n"
        "- Gap-Aware Personalized Career Roadmaps\n"
        "- Multi-Category Personalized Interview Question Generation\n"
    ),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Auth", "description": "User registration, authentication, and session identity."},
        {"name": "Resumes", "description": "Resume PDF upload, extraction, listing, and deletion."},
        {"name": "Resume Analysis", "description": "AI-driven career profiling and structured skill extraction."},
        {"name": "ATS", "description": "Applicant Tracking System compatibility scoring and feedback."},
        {"name": "Job Analysis", "description": "Resume vs Job Description comparison and match scoring."},
        {"name": "Skill Gap", "description": "Deterministic skill normalization and role gap categorization."},
        {"name": "Career Readiness", "description": "Multi-factor 0-100 career readiness score and recommendations."},
        {"name": "Career Roadmap", "description": "Personalized phased upskilling roadmap generation."},
        {"name": "Interview Prep", "description": "Personalized 7-category interview question generation."},
    ],
)

# CORS configuration — explicit origins so browsers accept Authorization headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Consistent error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
        },
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "success": False,
            "message": "Validation error",
            "detail": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An unexpected internal server error occurred.",
        },
    )


# Root health / info endpoint
@app.get("/", tags=["Health"], summary="API Health and Status")
def root():
    return {
        "success": True,
        "message": "AI-Powered Career Intelligence Platform API is active",
        "version": settings.VERSION,
        "docs_url": "/docs",
    }


# Include modular routers under API_V1_STR (/api)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(resume_router, prefix=settings.API_V1_STR)
app.include_router(analysis_router, prefix=settings.API_V1_STR)
app.include_router(job_analysis_router, prefix=settings.API_V1_STR)
app.include_router(skill_gap_router, prefix=settings.API_V1_STR)
app.include_router(career_readiness_router, prefix=settings.API_V1_STR)
app.include_router(career_roadmap_router, prefix=settings.API_V1_STR)
app.include_router(interview_router, prefix=settings.API_V1_STR)
app.include_router(interview_session_router, prefix=settings.API_V1_STR)
