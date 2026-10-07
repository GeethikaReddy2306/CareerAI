import json
import logging
from typing import Callable, TypeVar
from openai import OpenAI
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

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
    global _openai_quota_exhausted
    client = get_openai_client()
    if client is None:
        return fallback_factory()

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
        parsed_json = json.loads(content)
        validated = schema_cls.model_validate(parsed_json)
        return validated

    except Exception as exc:
        err_msg = str(exc).lower()
        if "insufficient_quota" in err_msg or "credit_balance_exhausted" in err_msg or "429" in err_msg:
            _openai_quota_exhausted = True
            logger.warning("OpenAI quota exhausted. Switching to deterministic fallback engine for session.")
        else:
            logger.warning(
                f"Structured AI call failed for {schema_cls.__name__} ({exc}). Using fallback.",
                exc_info=True,
            )
        return fallback_factory()

