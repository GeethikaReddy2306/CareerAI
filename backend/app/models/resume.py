# MongoDB: resumes collection stub
# Documents have shape:
# {
#   "_id": ObjectId,
#   "user_id": ObjectId,        # reference to users._id
#   "original_filename": str,
#   "file_path": str,
#   "file_type": str,
#   "file_size": int,
#   "extracted_text": str | None,
#   "uploaded_at": datetime,
#   "updated_at": datetime,
# }

COLLECTION = "resumes"
