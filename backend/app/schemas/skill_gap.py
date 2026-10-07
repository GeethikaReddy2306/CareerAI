from pydantic import BaseModel, Field


class SkillGapRequest(BaseModel):
    resume_id: int = Field(..., description="ID of the resume to analyze")
    target_role: str = Field(..., min_length=2, max_length=255, description="Target career role (e.g. Backend Developer)")
    target_skills: list[str] | None = Field(
        default=None,
        description="Optional list of skills required for the target role. If omitted, determined automatically.",
    )


class PrioritizedSkillItem(BaseModel):
    skill: str = Field(..., description="Skill name")
    category: str = Field(..., description="Strong, Intermediate, Weak, or Missing")
    priority: str = Field(..., description="High, Medium, or Low")
    reason: str = Field(..., description="Rationale for the prioritization")


class SkillGapResponse(BaseModel):
    target_role: str = Field(..., description="Evaluated target role")
    strong: list[str] = Field(default_factory=list, description="Skills where candidate shows strong proficiency")
    intermediate: list[str] = Field(default_factory=list, description="Skills where candidate has moderate familiarity")
    weak: list[str] = Field(default_factory=list, description="Skills mentioned superficially or needing deeper practice")
    missing: list[str] = Field(default_factory=list, description="Required role skills absent from resume")
    prioritized_skills: list[PrioritizedSkillItem] = Field(
        default_factory=list, description="Prioritized list of skills with action rationale"
    )

