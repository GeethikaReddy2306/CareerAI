from datetime import datetime
from typing import TYPE_CHECKING, Any
from sqlalchemy import DateTime, ForeignKey, Integer, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.resume import Resume


class JobAnalysis(Base):
    __tablename__ = "job_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    match_score: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    partial_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    important_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    interview_topics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recommendations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    resume: Mapped["Resume"] = relationship("Resume")

    def __repr__(self) -> str:
        return f"<JobAnalysis id={self.id} resume_id={self.resume_id} match_score={self.match_score}>"

