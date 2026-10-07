from datetime import datetime
from typing import TYPE_CHECKING, Any
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.resume import Resume


class ResumeAnalysis(Base):
    __tablename__ = "resume_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resume_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    education: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    projects: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    certifications: Mapped[list[str | dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    work_experience: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    strengths: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    weaknesses: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    suggested_roles: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    ats_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ats_feedback: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    resume: Mapped["Resume"] = relationship("Resume", back_populates="analysis")

    def __repr__(self) -> str:
        return f"<ResumeAnalysis id={self.id} resume_id={self.resume_id} ats_score={self.ats_score}>"

