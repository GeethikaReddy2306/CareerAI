"""
MongoDB connection module.

Usage:
    from app.core.database import get_db

    # In FastAPI dependency:
    def my_route(db: Annotated[Database, Depends(get_db)]):
        users = db["users"].find_one({"email": email})

The client is opened once at application startup (via lifespan in main.py)
and closed cleanly on shutdown. All collections are accessed via db[name].
"""
import logging
import re
from fastapi import HTTPException, status
from pymongo import MongoClient
from pymongo.database import Database
from app.core.config import settings

logger = logging.getLogger("career_platform")

# Module-level client & db handle — initialised in lifespan, accessible via get_db().
_client: MongoClient | None = None
_db: Database | None = None


def _mask_url(url: str) -> str:
    """Mask credentials in connection string for safe logging."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", url)


def connect_to_mongo() -> None:
    """Open the MongoDB connection and create indexes. Call once at startup."""
    global _client, _db
    if _db is not None:
        return

    # Check for placeholder or unconfigured URL
    if not settings.MONGODB_URL or "your_mongodb_atlas_connection_uri" in settings.MONGODB_URL:
        logger.warning(
            "MONGODB_URL contains placeholder. Set your MongoDB Atlas URI in backend/.env"
        )
        return

    try:
        _client = MongoClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=8_000,
            connectTimeoutMS=8_000,
        )
        _db = _client[settings.MONGODB_DATABASE]

        # Verify connectivity
        _client.admin.command("ping")
        logger.info(
            "MongoDB connected successfully: db=%s, host=%s",
            settings.MONGODB_DATABASE,
            _mask_url(settings.MONGODB_URL),
        )

        _ensure_indexes()
    except Exception as exc:
        logger.error("Failed to connect to MongoDB: %s", exc)
        _client = None
        _db = None
        raise


def close_mongo_connection() -> None:
    """Close the MongoDB connection. Call once at shutdown."""
    global _client, _db
    if _client:
        try:
            _client.close()
        except Exception:
            pass
        logger.info("MongoDB connection closed.")
    _client = None
    _db = None


def check_database_connectivity() -> bool:
    """Verifies actual database connectivity with a lightweight ping command."""
    global _client
    if _client is None:
        return False
    try:
        _client.admin.command("ping")
        return True
    except Exception:
        return False


def get_db() -> Database:
    """
    FastAPI dependency — returns the active MongoDB Database instance.
    Raises HTTP 503 if database is not connected.
    """
    if _db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is unavailable. Please verify MONGODB_URL in backend/.env.",
        )
    return _db


def set_test_db(db: Database | None) -> None:
    """Helper for test suites to inject a mock or test database instance."""
    global _db
    _db = db


def _ensure_indexes() -> None:
    """Create indexes on startup (idempotent — safe to re-run)."""
    db = _db
    if db is None:
        return

    try:
        # users: unique email
        db["users"].create_index("email", unique=True, background=True)

        # resumes: filter by owner
        db["resumes"].create_index("user_id", background=True)

        # resume_analyses: unique per resume
        db["resume_analyses"].create_index("resume_id", unique=True, background=True)

        # job_analyses: filter by user + resume
        db["job_analyses"].create_index([("user_id", 1), ("resume_id", 1)], background=True)

        # roadmaps: filter by user + resume, latest first
        db["roadmaps"].create_index(
            [("user_id", 1), ("resume_id", 1), ("created_at", -1)], background=True
        )

        # interview_questions: filter by user + resume
        db["interview_questions"].create_index(
            [("user_id", 1), ("resume_id", 1)], background=True
        )

        logger.info("MongoDB indexes verified/created.")
    except Exception as exc:
        logger.warning("Could not ensure indexes: %s", exc)
