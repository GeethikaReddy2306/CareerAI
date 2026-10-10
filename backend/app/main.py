from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import (
    check_database_connectivity,
    close_mongo_connection,
    connect_to_mongo,
    get_db,
)
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
    # ── Startup ────────────────────────────────────────────────────────────────
    # Ensure upload directories exist
    settings.resumes_upload_path.mkdir(parents=True, exist_ok=True)
    logger.info("Application startup: verified storage directories.")

    # Connect to MongoDB Atlas
    try:
        connect_to_mongo()
    except Exception as exc:
        logger.warning(
            "MongoDB Atlas connection not established on startup: %s. Application is running. Set your Atlas URI in backend/.env to enable database operations.",
            exc,
        )

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    close_mongo_connection()
    logger.info("Application shutdown complete.")


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

# CORS — origins come from ALLOWED_ORIGINS env var (comma-separated).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
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
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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


@app.get("/health", tags=["Health"], summary="Health check")
def health_check():
    """Liveness probe — also verifies MongoDB is reachable."""
    is_connected = check_database_connectivity()
    return {
        "status": "ok",
        "version": settings.VERSION,
        "database": "connected" if is_connected else "disconnected",
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
