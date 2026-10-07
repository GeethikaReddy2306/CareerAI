from pydantic import BaseModel, Field


class CareerReadinessBreakdown(BaseModel):
    skill_match: float = Field(..., description="Alignment of candidate skills with target role requirements (35%)")
    resume_quality: float = Field(..., description="Structural clarity, completeness, and ATS readiness (20%)")
    project_experience: float = Field(..., description="Depth, complexity, and technology overlap of projects (15%)")
    interview_readiness: float = Field(..., description="Preparedness across technical and foundational domains (15%)")
    experience_relevance: float = Field(..., description="Seniority, tenure, and responsibility alignment (15%)")


class CareerReadinessResponse(BaseModel):
    overall_score: int = Field(..., ge=0, le=100, description="Overall career readiness score (0-100)")
    target_role: str = Field(..., description="Evaluated target role")
    breakdown: CareerReadinessBreakdown
    strengths: list[str] = Field(default_factory=list, description="Key candidate competitive advantages")
    areas_to_improve: list[str] = Field(default_factory=list, description="Critical growth opportunities")
    recommendations: list[str] = Field(default_factory=list, description="Concrete next steps to attain readiness")

