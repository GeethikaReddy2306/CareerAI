import json
import logging
import re
from typing import Any, Callable, Literal, TypeVar
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError
from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
AIStatus = Literal[
    "success",
    "not_configured",
    "configuration_error",
    "permission_error",
    "timeout",
    "rate_limited",
    "quota_exhausted",
    "connection_error",
    "invalid_request",
    "model_unavailable",
    "invalid_output",
    "provider_error",
]


def is_openai_configured() -> bool:
    """Check whether a non-placeholder API key is configured.

    This intentionally does not claim the credential is valid; validity is
    established only by a provider request and reported through ``AIStatus``.
    """
    api_key = (settings.OPENAI_API_KEY or "").strip()
    return bool(api_key and not api_key.startswith("mock") and not api_key.startswith("your-openai"))


def get_openai_client() -> OpenAI | None:
    """Create and return an OpenAI client if configured, else None."""
    if not is_openai_configured():
        return None
    return OpenAI(
        api_key=settings.OPENAI_API_KEY.strip(),
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
        max_retries=settings.OPENAI_MAX_RETRIES,
    )


def _provider_error_code(exc: Exception) -> str | None:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            nested = error.get("code")
            if isinstance(nested, str) and nested:
                return nested
    return None


def _classify_ai_error(exc: Exception) -> AIStatus:
    """Map provider failures to stable, client-safe categories.

    The detailed exception remains in server logs; callers only receive the category.
    """
    code = _provider_error_code(exc)
    if code == "insufficient_quota":
        return "quota_exhausted"
    if isinstance(exc, AuthenticationError) or code in {"invalid_api_key", "invalid_api_key_format"}:
        return "configuration_error"
    if isinstance(exc, PermissionDeniedError):
        return "permission_error"
    if isinstance(exc, APITimeoutError):
        return "timeout"
    if isinstance(exc, APIConnectionError):
        return "connection_error"
    if isinstance(exc, RateLimitError):
        return "rate_limited"
    if isinstance(exc, BadRequestError):
        return "invalid_request"
    if isinstance(exc, APIStatusError):
        if exc.status_code == 404:
            return "model_unavailable"
        if exc.status_code == 400:
            return "invalid_request"
        if exc.status_code == 401:
            return "configuration_error"
        if exc.status_code == 403:
            return "permission_error"
        if exc.status_code == 429:
            return "rate_limited"
    if isinstance(exc, (json.JSONDecodeError, ValidationError, ValueError)):
        return "invalid_output"
    return "provider_error"


def _parse_json_object(content: str) -> Any:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def try_structured_ai(
    prompt: str,
    system_prompt: str,
    schema_cls: type[T],
    temperature: float = 0.2,
) -> tuple[T | None, AIStatus]:
    """Run a structured AI request without concealing why it was unavailable.

    This is intentionally separate from ``call_structured_ai`` so established
    features can keep their deterministic fallback while user-facing interview
    flows can accurately label provider failures.
    """
    client = get_openai_client()
    if client is None:
        return None, "not_configured"

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        content = response.choices[0].message.content or "{}"
        return schema_cls.model_validate(_parse_json_object(content)), "success"
    except Exception as exc:
        failure = _classify_ai_error(exc)
        # Never log the raw provider exception: authentication errors can
        # include credential fragments. These fields are enough to diagnose
        # the failure without exposing a secret.
        logger.warning(
            "Structured AI call failed: schema=%s category=%s exception_type=%s status=%s code=%s",
            schema_cls.__name__,
            failure,
            type(exc).__name__,
            getattr(exc, "status_code", None),
            getattr(exc, "code", None),
        )
        return None, failure


def call_structured_ai(
    prompt: str,
    system_prompt: str,
    schema_cls: type[T],
    fallback_factory: Callable[[], T],
    temperature: float = 0.2,
) -> T:
    """Execute a structured LLM completion request with JSON validation.

    If OpenAI is not configured, or if any API error, rate limit, timeout, or
    schema mismatch occurs, gracefully returns fallback_factory() without crashing.
    """
    result, _status = try_structured_ai(
        prompt=prompt,
        system_prompt=system_prompt,
        schema_cls=schema_cls,
        temperature=temperature,
    )
    return result if result is not None else fallback_factory()

