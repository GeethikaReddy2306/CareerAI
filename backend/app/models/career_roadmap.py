from datetime import datetime
from typing import TYPE_CHECKING, Any
from sqlalchemy import DateTime, ForeignKey, Integer, String, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.resume import Resume


class CareerRoadmap(Base):
    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_role: Mapped[str] = mapped_column(String(255), nullable=False)
    current_level: Mapped[str] = mapped_column(String(64), nullable=False)
    roadmap_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

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
        return f"<CareerRoadmap id={self.id} target_role={self.target_role}>"

