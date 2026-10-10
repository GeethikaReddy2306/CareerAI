import json
import logging

from openai import OpenAI

from app.core.config import settings
from app.services.ai_service import is_openai_configured

logger = logging.getLogger(__name__)

REVIEW_PROMPT = """You are an expert technical resume reviewer and ATS specialist.
Analyze the resume text below and return ONLY valid JSON, no markdown fences, no preamble.

Return this exact JSON shape:
{
  "clarity_score": <int 0-100, how clearly the resume communicates>,
  "impact_score": <int 0-100, how well it demonstrates measurable impact>,
  "grammar_issues": [{"line": "<exact quoted line>", "issue": "<what is wrong>", "fix": "<corrected version>"}],
  "weak_bullets": [{"line": "<exact quoted line>", "why_weak": "<reason>", "improved_version": "<rewrite>"}],
  "missing_impact_keywords": ["<skill or keyword the target role would expect but resume lacks>"],
  "overall_feedback": "<2-3 sentence summary of the resume overall quality and biggest opportunity for improvement>"
}

Rules:
- Only quote lines that actually appear verbatim in the resume text. Never invent content.
- Limit weak_bullets to at most 5 of the weakest examples.
- If there are no grammar issues, return an empty list for grammar_issues.
- Be strict but fair.

RESUME TEXT:
{resume_text}
"""

FALLBACK_REVIEW = {
    "clarity_score": None,
    "impact_score": None,
    "grammar_issues": [],
    "weak_bullets": [],
    "missing_impact_keywords": [],
    "overall_feedback": "AI review is unavailable. Showing the ATS score only.",
}


def _normalize_review(parsed: dict) -> dict:
    return {
        "clarity_score": parsed.get("clarity_score"),
        "impact_score": parsed.get("impact_score"),
        "grammar_issues": parsed.get("grammar_issues") or [],
        "weak_bullets": parsed.get("weak_bullets") or [],
        "missing_impact_keywords": parsed.get("missing_impact_keywords") or [],
        "overall_feedback": parsed.get("overall_feedback") or FALLBACK_REVIEW["overall_feedback"],
    }


def get_llm_review(resume_text: str) -> dict:
    """Optional OpenAI-powered deep review. Never raises — callers always get a dict.

    Returns FALLBACK_REVIEW if OpenAI is not configured, the call fails, or the
    response is not valid JSON — this must never crash or block the main ATS score.
    """
    if not is_openai_configured():
        return FALLBACK_REVIEW

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY.strip(), timeout=30.0, max_retries=0)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": REVIEW_PROMPT.replace("{resume_text}", resume_text or ""),
                }
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return FALLBACK_REVIEW
        return _normalize_review(parsed)

    except Exception:
        logger.exception("OpenAI resume deep-review failed; returning fallback")
        return FALLBACK_REVIEW
