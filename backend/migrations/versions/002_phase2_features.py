"""phase2 features

Revision ID: 002_phase2_features
Revises: 001_initial_schema
Create Date: 2026-09-20 16:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_phase2_features"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. job_analyses table
    op.create_table(
        "job_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False),
        sa.Column("matched_skills", sa.JSON(), nullable=False),
        sa.Column("partial_skills", sa.JSON(), nullable=False),
        sa.Column("missing_skills", sa.JSON(), nullable=False),
        sa.Column("important_keywords", sa.JSON(), nullable=False),
        sa.Column("interview_topics", sa.JSON(), nullable=False),
        sa.Column("recommendations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_analyses_resume_id"), "job_analyses", ["resume_id"], unique=False)
    op.create_index(op.f("ix_job_analyses_user_id"), "job_analyses", ["user_id"], unique=False)

    # 2. roadmaps table
    op.create_table(
        "roadmaps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("target_role", sa.String(length=255), nullable=False),
        sa.Column("current_level", sa.String(length=64), nullable=False),
        sa.Column("roadmap_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roadmaps_resume_id"), "roadmaps", ["resume_id"], unique=False)
    op.create_index(op.f("ix_roadmaps_user_id"), "roadmaps", ["user_id"], unique=False)

    # 3. interview_questions table
    op.create_table(
        "interview_questions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("target_role", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interview_questions_resume_id"), "interview_questions", ["resume_id"], unique=False)
    op.create_index(op.f("ix_interview_questions_user_id"), "interview_questions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_interview_questions_user_id"), table_name="interview_questions")
    op.drop_index(op.f("ix_interview_questions_resume_id"), table_name="interview_questions")
    op.drop_table("interview_questions")

    op.drop_index(op.f("ix_roadmaps_user_id"), table_name="roadmaps")
    op.drop_index(op.f("ix_roadmaps_resume_id"), table_name="roadmaps")
    op.drop_table("roadmaps")

    op.drop_index(op.f("ix_job_analyses_user_id"), table_name="job_analyses")
    op.drop_index(op.f("ix_job_analyses_resume_id"), table_name="job_analyses")
    op.drop_table("job_analyses")

