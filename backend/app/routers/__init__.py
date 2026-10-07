from app.routers.auth import router as auth_router
from app.routers.resume import router as resume_router
from app.routers.analysis import router as analysis_router
from app.routers.job_analysis import router as job_analysis_router
from app.routers.skill_gap import router as skill_gap_router
from app.routers.career_readiness import router as career_readiness_router
from app.routers.career_roadmap import router as career_roadmap_router
from app.routers.interview import router as interview_router
from app.routers.interview import session_router as interview_session_router

__all__ = [
    "auth_router",
    "resume_router",
    "analysis_router",
    "job_analysis_router",
    "skill_gap_router",
    "career_readiness_router",
    "career_roadmap_router",
    "interview_router",
    "interview_session_router",
]
