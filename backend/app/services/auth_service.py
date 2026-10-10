from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.db_helpers import serialize_doc, str_id, to_object_id, utcnow
from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.auth import TokenResponse, UserLoginRequest, UserRegisterRequest

_COLLECTION = "users"


def get_user_by_email(db: Database, email: str) -> dict[str, Any] | None:
    """Fetch a user document by email (case-normalised)."""
    doc = db[_COLLECTION].find_one({"email": email.lower().strip()})
    return serialize_doc(doc)


def get_user_by_id(db: Database, user_id: str) -> dict[str, Any] | None:
    """Fetch a user document by ObjectId string."""
    try:
        oid = to_object_id(user_id)
    except ValueError:
        return None
    doc = db[_COLLECTION].find_one({"_id": oid})
    return serialize_doc(doc)


def register_user(db: Database, request: UserRegisterRequest) -> dict[str, Any]:
    """Register a new user. Raises 400 on duplicate email."""
    now = utcnow()
    doc = {
        "name": request.name.strip(),
        "email": request.email.lower().strip(),
        "password_hash": hash_password(request.password),
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = db[_COLLECTION].insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


def authenticate_user(db: Database, request: UserLoginRequest) -> TokenResponse:
    """Validate credentials and return a JWT bearer token."""
    normalized_email = request.email.lower().strip()
    doc = db[_COLLECTION].find_one({"email": normalized_email})

    if not doc or not verify_password(request.password, doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = {"sub": str(doc["_id"]), "email": doc["email"]}
    access_token = create_access_token(data=token_data)
    return TokenResponse(access_token=access_token, token_type="bearer")
