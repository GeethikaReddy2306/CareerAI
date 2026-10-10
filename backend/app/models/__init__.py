"""
MongoDB collection stubs.

SQLAlchemy ORM models have been removed.
Collections are accessed directly via `get_db()["collection_name"]`.
This file is kept as a namespace/documentation reference only.

Collections in use:
  users               — user accounts
  resumes             — uploaded resume metadata + extracted text
  resume_analyses     — AI analysis + ATS scoring results
  job_analyses        — job description match results
  roadmaps            — career roadmaps
  interview_questions — generated interview questions
"""

USERS_COLLECTION = "users"
RESUMES_COLLECTION = "resumes"
RESUME_ANALYSES_COLLECTION = "resume_analyses"
JOB_ANALYSES_COLLECTION = "job_analyses"
ROADMAPS_COLLECTION = "roadmaps"
INTERVIEW_QUESTIONS_COLLECTION = "interview_questions"
