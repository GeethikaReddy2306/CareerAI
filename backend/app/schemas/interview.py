from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InterviewQuestionsRequest(BaseModel):
    resume_id: str | int = Field(..., description="Candidate resume ID")
    target_role: str = Field(..., min_length=2, max_length=255, description="Target job title or role")
    job_description: str | None = Field(default=None, description="Optional job description text for deeper tailoring")
    question_count: int = Field(default=15, ge=5, le=50, description="Total number of questions to generate (5-50)")
    session_id: str | None = Field(default=None, description="Continue an existing interview session")


class InterviewQuestionItem(BaseModel):
    question: str = Field(..., description="The interview question")
    category: str = Field(
        ...,
        description="Category: Technical, Resume Based, Project Based, Role Specific, Skill Gap Based, Behavioral, or HR",
    )
    difficulty: str = Field(..., description="Difficulty level: Easy, Medium, or Hard")
    topic: str = Field(..., description="Specific technology, competency, or conceptual topic")

    model_config = ConfigDict(from_attributes=True)


class InterviewQuestionsResponse(BaseModel):
    questions: list[InterviewQuestionItem] = Field(
        default_factory=list, description="Personalized questions categorized across 7 core dimensions"
    )
    session_id: str | None = None
    requested_count: int | None = Field(default=None, ge=0)
    returned_count: int = Field(default=0, ge=0, description="Number of validated unique questions returned")
    generation_mode: str = Field(default="ai", description="ai, demo, profile_based, saved, mixed, or error")
    generation_notice: str | None = Field(default=None, description="Safe explanation when AI generation was unavailable")
    failure_category: str | None = Field(default=None, description="Safe provider failure category, when applicable")


class MockAnswerRequest(BaseModel):
    question: str = Field(..., min_length=8, description="Interview question that was asked")
    answer: str = Field(..., min_length=1, description="Candidate spoken or written answer")
    category: str = Field(default="Technical", description="Question category")
    topic: str = Field(default="General", description="Topic the question covers")
    target_role: str | None = Field(default=None, description="Optional target role for context")
    session_id: str | None = Field(default=None, description="Interview session that owns this answer")


class MockAnswerEvaluation(BaseModel):
    score: int = Field(..., ge=0, le=100, description="Answer quality score (0-100)")
    verdict: str = Field(..., description="Short verdict: Strong, Adequate, or Needs Work")
    feedback: str = Field(..., description="Coach-style feedback on the answer")
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)
    evaluation_mode: str = Field(default="ai", description="ai, demo, or profile_based")
    evaluation_notice: str | None = None
    failure_category: str | None = None


class InterviewSessionResponse(BaseModel):
    id: str
    resume_id: str
    target_role: str
    job_description: str | None = None
    questions: list[InterviewQuestionItem] = Field(default_factory=list)
    answers: list[dict[str, Any]] = Field(default_factory=list)
    generation_mode: str = "unknown"
    generation_notice: str | None = None
    failure_category: str | None = None

