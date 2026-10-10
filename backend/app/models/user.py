# MongoDB: users collection stub
# Documents have shape:
# {
#   "_id": ObjectId,
#   "name": str,
#   "email": str,           # unique, lowercase-normalised
#   "password_hash": str,
#   "created_at": datetime,
#   "updated_at": datetime,
# }

COLLECTION = "users"
