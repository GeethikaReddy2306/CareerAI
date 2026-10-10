from pydantic import BaseModel, ConfigDict, Field


class RoadmapCreateRequest(BaseModel):
    resume_id: str | int = Field(..., description="ID of the candidate resume")
    target_role: str = Field(..., min_length=2, max_length=255, description="Target career role")


class RoadmapPhase(BaseModel):
    phase: int = Field(..., description="Sequential phase number")
    title: str = Field(..., description="Phase focus area")
    description: str = Field(..., description="Summary of phase goals and career impact")
    skills: list[str] = Field(default_factory=list, description="Target skills to master in this phase")
    topics: list[str] = Field(default_factory=list, description="Specific learning topics and sub-modules")
    projects: list[str] = Field(default_factory=list, description="Hands-on portfolio projects to build")
    estimated_weeks: int = Field(..., ge=1, description="Estimated duration in weeks")
    priority: str = Field(..., description="Priority: High, Medium, or Low")


class RoadmapResponse(BaseModel):
    id: str | None = None
    resume_id: str
    target_role: str
    current_level: str
    roadmap: list[RoadmapPhase] = Field(default_factory=list, description="Chronological career milestones")

    model_config = ConfigDict(from_attributes=False)
