# MongoDB: job_analyses collection stub
# Documents have shape:
# {
#   "_id": ObjectId,
#   "user_id": ObjectId,
#   "resume_id": ObjectId,
#   "job_description": str,
#   "match_score": int,
#   "matched_skills": list[str],
#   "partial_skills": list[str],
#   "missing_skills": list[str],
#   "important_keywords": list[str],
#   "interview_topics": list[str],
#   "recommendations": list[str],
#   "created_at": datetime,
#   "updated_at": datetime,
# }

COLLECTION = "job_analyses"
