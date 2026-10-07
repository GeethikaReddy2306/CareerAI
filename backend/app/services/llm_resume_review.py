import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

REVIEW_PROMPT = """You are an expert technical resume reviewer and ATS specialist.
Analyze the resume text below and return ONLY valid JSON, no markdown fences, no preamble.

Return this exact JSON shape:
{{
  "clarity_score": <int 0-100>,
  "impact_score": <int 0-100>,
  "grammar_issues": [{{"line": "<exact quoted line>", "issue": "<what's wrong>", "fix": "<corrected version>"}}],
  "weak_bullets": [{{"line": "<exact quoted line>", "why_weak": "<reason>", "improved_version": "<rewrite>"}}],
  "missing_impact_keywords": ["<skill or keyword the target role would expect but resume lacks>"],
  "overall_feedback": "<2-3 sentence summary>"
}}

Only quote lines that actually appear verbatim in the resume text. Do not invent content.

RESUME TEXT:
{resume_text}
"""

FALLBACK_REVIEW = {
    "clarity_score": None,
    "impact_score": None,
    "grammar_issues": [],
    "weak_bullets": [],
    "missing_impact_keywords": [],
    "overall_feedback": "AI review is unavailable. Showing the deterministic ATS score only.",
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
    """Optional Anthropic review. Never raises — callers always get a dict."""
    api_key = (settings.ANTHROPIC_API_KEY or "").strip()
    if not api_key:
        return FALLBACK_REVIEW

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": REVIEW_PROMPT.replace("{resume_text}", resume_text or ""),
                }
            ],
        )
        raw = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            return FALLBACK_REVIEW
        return _normalize_review(parsed)
    except Exception:
        logger.exception("Anthropic resume review failed; returning fallback")
        return FALLBACK_REVIEW
