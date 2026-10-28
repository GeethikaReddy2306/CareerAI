import json
import logging
from typing import Callable, Literal, TypeVar
from openai import OpenAI
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
AIStatus = Literal[
    "success",
    "not_configured",
    "configuration_error",
    "timeout",
    "rate_limited",
    "invalid_output",
    "provider_error",
]

_openai_quota_exhausted = False


def is_openai_configured() -> bool:
    """Check if a real OpenAI API key is configured and active."""
    global _openai_quota_exhausted
    if _openai_quota_exhausted:
        return False
    api_key = (settings.OPENAI_API_KEY or "").strip()
    return bool(api_key and not api_key.startswith("mock") and not api_key.startswith("your-openai"))


def get_openai_client() -> OpenAI | None:
    """Create and return an OpenAI client if configured, else None."""
    if not is_openai_configured():
        return None
    return OpenAI(api_key=settings.OPENAI_API_KEY.strip(), timeout=10.0, max_retries=0)


def _classify_ai_error(exc: Exception) -> AIStatus:
    """Map provider failures to stable, client-safe categories.

    The detailed exception remains in server logs; callers only receive the category.
    """
    message = str(exc).casefold()
    if any(value in message for value in ("timeout", "timed out", "readtimeout", "apitimeouterror")):
        return "timeout"
    if any(value in message for value in ("invalid api key", "incorrect api key", "authentication", "unauthorized", "401")):
        return "configuration_error"
    if any(value in message for value in ("insufficient_quota", "credit_balance_exhausted", "rate limit", "429")):
        return "rate_limited"
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return "invalid_output"
    return "provider_error"


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
    global _openai_quota_exhausted
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
        return schema_cls.model_validate(json.loads(content)), "success"
    except Exception as exc:
        failure = _classify_ai_error(exc)
        if failure == "rate_limited":
            _openai_quota_exhausted = True
        logger.warning(
            "Structured AI call failed for %s (%s)", schema_cls.__name__, failure,
            exc_info=True,
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

