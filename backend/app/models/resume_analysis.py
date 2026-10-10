# MongoDB: resume_analyses collection stub
# Documents have shape:
# {
#   "_id": ObjectId,
#   "resume_id": ObjectId,   # unique reference to resumes._id
#   "summary": str | None,
#   "skills": list[str] | None,
#   "education": list[dict] | None,
#   "projects": list[dict] | None,
#   "certifications": list | None,
#   "work_experience": list[dict] | None,
#   "strengths": list[str] | None,
#   "weaknesses": list[str] | None,
#   "experience_level": str | None,
#   "suggested_roles": list[str] | None,
#   "ats_score": int | None,
#   "ats_feedback": dict | None,
#   "created_at": datetime,
#   "updated_at": datetime,
# }

COLLECTION = "resume_analyses"
