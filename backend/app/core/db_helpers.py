"""
MongoDB ↔ API boundary helpers.

- ObjectId to/from str conversion
- Document serialisation (rename _id → id, convert ObjectId fields)
"""
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId


def to_object_id(id_str: str) -> ObjectId:
    """
    Convert a 24-char hex string to a BSON ObjectId.
    Raises ValueError with a clean message if invalid.
    """
    try:
        return ObjectId(id_str)
    except Exception:
        raise ValueError(f"Invalid id format: '{id_str}'")


def str_id(obj_id: Any) -> str:
    """Return a string representation of an ObjectId (or pass-through str)."""
    return str(obj_id)


def serialize_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Convert a raw MongoDB document for API serialisation:
    - Renames '_id' to 'id'
    - Converts ObjectId values to str
    - Returns None if doc is None
    """
    if doc is None:
        return None
    result: dict[str, Any] = {}
    for key, value in doc.items():
        out_key = "id" if key == "_id" else key
        result[out_key] = _convert_value(value)
    return result


def _convert_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {("id" if k == "_id" else k): _convert_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert_value(item) for item in value]
    return value


def utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)

