from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class EducationItem(BaseModel):
    degree: str = Field(..., description="Degree or program title")
    institution: str = Field(..., description="College or university name")
    year: str | None = Field(default=None, description="Graduation year or date range")


class ProjectItem(BaseModel):
    name: str = Field(..., description="Project name")
    description: str = Field(..., description="Description of the project")
    technologies: list[str] = Field(default_factory=list, description="Technologies and tools used")


class WorkExperienceItem(BaseModel):
    company: str = Field(..., description="Company or organization name")
    role: str = Field(..., description="Job title or role")
    duration: str | None = Field(default=None, description="Employment duration")
    responsibilities: list[str] = Field(default_factory=list, description="List of duties or accomplishments")


class AIResumeAnalysisResult(BaseModel):
    summary: str = Field(default="", description="Short professional summary")
    skills: list[str] = Field(default_factory=list, description="Technical and professional skills")
    education: list[EducationItem] = Field(default_factory=list, description="Academic history")
    projects: list[ProjectItem] = Field(default_factory=list, description="Notable projects")
    certifications: list[str] = Field(default_factory=list, description="Certifications and licenses")
    work_experience: list[WorkExperienceItem] = Field(default_factory=list, description="Professional experience")
    strengths: list[str] = Field(default_factory=list, description="Candidate strengths")
    weaknesses: list[str] = Field(default_factory=list, description="Areas for candidate improvement")
    experience_level: str = Field(
        default="Fresher",
        description="Candidate level: Student, Fresher, Junior, Mid-Level, or Senior",
    )
    suggested_roles: list[str] = Field(default_factory=list, description="Recommended job titles")


class ATSIssue(BaseModel):
    message: str
    detail: str


class ATSCategory(BaseModel):
    name: str
    score_percent: int
    status: str
    issues: list[ATSIssue] = []


class ATSBreakdown(BaseModel):
    keyword_relevance: float = Field(..., description="Relevance and breadth of industry keywords (30%)")
    structure: float = Field(..., description="Logical structure and readability (20%)")
    required_sections: float = Field(..., description="Presence of key resume sections (15%)")
    skills_clarity: float = Field(..., description="Clear skills categorization and density (15%)")
    experience_quality: float = Field(..., description="Action verbs and measurable impact (10%)")
    formatting: float = Field(..., description="Basic text formatting and layout hygiene (10%)")


class ATSScoreResponse(BaseModel):
    score: int = Field(..., ge=0, le=100, description="Overall ATS compatibility score (0-100)")
    breakdown: ATSBreakdown
    missing_sections: list[str] = Field(default_factory=list, description="Sections not detected")
    detected_sections: list[str] = Field(default_factory=list, description="Standard sections found")
    suggestions: list[str] = Field(default_factory=list, description="Actionable recommendations")
    categories: list[ATSCategory] = []
    ai_review: dict[str, Any] | None = Field(
        default=None,
        description="Optional OpenAI-powered deep review; never blocks the deterministic score",
    )


class ResumeAnalysisDetailResponse(BaseModel):
    id: str
    resume_id: str
    summary: str | None = None
    skills: list[str] | None = None
    education: list[EducationItem] | None = None
    projects: list[ProjectItem] | None = None
    certifications: list[Any] | None = None
    work_experience: list[WorkExperienceItem] | None = None
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    experience_level: str | None = None
    suggested_roles: list[str] | None = None
    ats_score: int | None = None
    ats_feedback: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=False)
