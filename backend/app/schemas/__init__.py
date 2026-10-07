from app.schemas.auth import UserLoginRequest, UserRegisterRequest, TokenResponse
from app.schemas.user import UserResponse, UserMeResponse
from app.schemas.resume import ResumeResponse, ResumeDetailResponse, ResumeUploadResponse
from app.schemas.resume_analysis import (
    AIResumeAnalysisResult,
    ATSScoreResponse,
    ResumeAnalysisDetailResponse,
)
from app.schemas.job_analysis import JobAnalysisRequest, JobAnalysisResponse
from app.schemas.skill_gap import SkillGapRequest, PrioritizedSkillItem, SkillGapResponse
from app.schemas.career_readiness import CareerReadinessBreakdown, CareerReadinessResponse
from app.schemas.career_roadmap import RoadmapPhase, RoadmapResponse, RoadmapCreateRequest
from app.schemas.interview import (
    InterviewQuestionItem,
    InterviewQuestionsRequest,
    InterviewQuestionsResponse,
)
from app.schemas.common import APIResponse, ErrorResponse

__all__ = [
    "UserLoginRequest",
    "UserRegisterRequest",
    "TokenResponse",
    "UserResponse",
    "UserMeResponse",
    "ResumeResponse",
    "ResumeDetailResponse",
    "ResumeUploadResponse",
    "AIResumeAnalysisResult",
    "ATSScoreResponse",
    "ResumeAnalysisDetailResponse",
    "JobAnalysisRequest",
    "JobAnalysisResponse",
    "SkillGapRequest",
    "PrioritizedSkillItem",
    "SkillGapResponse",
    "CareerReadinessBreakdown",
    "CareerReadinessResponse",
    "RoadmapPhase",
    "RoadmapResponse",
    "RoadmapCreateRequest",
    "InterviewQuestionItem",
    "InterviewQuestionsRequest",
    "InterviewQuestionsResponse",
    "APIResponse",
    "ErrorResponse",
]
