from pydantic import BaseModel, ConfigDict, Field


class JobAnalysisRequest(BaseModel):
    resume_id: int = Field(..., description="ID of the candidate resume to compare")
    job_description: str = Field(
        ..., min_length=10, description="Job description text detailing requirements and responsibilities"
    )


class JobAnalysisResponse(BaseModel):
    id: int
    resume_id: int
    match_score: int = Field(..., ge=0, le=100, description="Overall match compatibility score (0-100)")
    matched_skills: list[str] = Field(default_factory=list, description="Skills present in both resume and JD")
    partial_skills: list[str] = Field(
        default_factory=list,
        description="Skills where candidate has foundational familiarity but JD seeks deeper expertise",
    )
    missing_skills: list[str] = Field(
        default_factory=list, description="Skills explicitly desired by JD but missing from resume"
    )
    important_keywords: list[str] = Field(
        default_factory=list, description="Important role-related and technical keywords extracted from JD"
    )
    interview_topics: list[str] = Field(
        default_factory=list, description="Suggested interview discussion topics based on the JD and candidate profile"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Targeted recommendations to improve alignment with this specific role"
    )

    model_config = ConfigDict(from_attributes=True)

