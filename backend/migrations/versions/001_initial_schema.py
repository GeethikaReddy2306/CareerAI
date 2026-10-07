"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-20 16:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # 2. resumes table
    op.create_table(
        "resumes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resumes_user_id"), "resumes", ["user_id"], unique=False)

    # 3. resume_analyses table
    op.create_table(
        "resume_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=True),
        sa.Column("education", sa.JSON(), nullable=True),
        sa.Column("projects", sa.JSON(), nullable=True),
        sa.Column("certifications", sa.JSON(), nullable=True),
        sa.Column("work_experience", sa.JSON(), nullable=True),
        sa.Column("strengths", sa.JSON(), nullable=True),
        sa.Column("weaknesses", sa.JSON(), nullable=True),
        sa.Column("experience_level", sa.String(length=64), nullable=True),
        sa.Column("suggested_roles", sa.JSON(), nullable=True),
        sa.Column("ats_score", sa.Integer(), nullable=True),
        sa.Column("ats_feedback", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resume_analyses_resume_id"), "resume_analyses", ["resume_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_resume_analyses_resume_id"), table_name="resume_analyses")
    op.drop_table("resume_analyses")
    op.drop_index(op.f("ix_resumes_user_id"), table_name="resumes")
    op.drop_table("resumes")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

