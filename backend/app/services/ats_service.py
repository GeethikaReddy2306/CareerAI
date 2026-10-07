import json
import logging

from openai import OpenAI

from app.core.config import settings
from app.schemas.resume_analysis import ATSBreakdown, ATSCategory, ATSIssue, ATSScoreResponse
from app.services.ai_service import is_openai_configured

logger = logging.getLogger(__name__)

ALL_STANDARD_SECTIONS = [
    "Contact Information", "Professional Summary", "Skills",
    "Education", "Work Experience", "Projects", "Certifications",
]

ATS_SYSTEM_PROMPT = """You are an expert ATS (Applicant Tracking System) resume evaluator and senior technical recruiter.
Analyze the resume text exactly as a real ATS parser + recruiter would.
Output ONLY a valid JSON object matching this EXACT shape:

{
  "score": <int 0-100, overall ATS compatibility>,
  "breakdown": {
    "keyword_relevance": <int 0-100>,
    "structure": <int 0-100>,
    "required_sections": <int 0-100>,
    "skills_clarity": <int 0-100>,
    "experience_quality": <int 0-100>,
    "formatting": <int 0-100>
  },
  "detected_sections": [<subset of: "Contact Information", "Professional Summary", "Skills", "Education", "Work Experience", "Projects", "Certifications">],
  "missing_sections": [<the remaining sections from that same list, not detected>],
  "suggestions": [<3-8 short, specific, actionable improvement suggestions>],
  "categories": [
    {
      "name": "Quantifying Impact",
      "score_percent": <int 0-100>,
      "status": "pass" or "issues",
      "issues": [{"message": "<short label>", "detail": "<exact quoted line from the resume that has the problem>"}]
    },
    {
      "name": "Repetition",
      "score_percent": <int 0-100>,
      "status": "pass" or "issues",
      "issues": [{"message": "<short label, e.g. 'Developed' used to start 4 bullets>", "detail": "<quoted example lines>"}]
    },
    {
      "name": "Spelling & Grammar",
      "score_percent": <int 0-100>,
      "status": "pass" or "issues",
      "issues": [{"message": "<what's wrong>", "detail": "<quoted line + correction>"}]
    },
    {
      "name": "Bullets Consistency",
      "score_percent": <int 0-100>,
      "status": "pass" or "issues",
      "issues": [{"message": "<what's inconsistent>", "detail": "<quoted examples>"}]
    }
  ],
  "ai_review": {
    "clarity_score": <int 0-100, how clearly the resume communicates>,
    "impact_score": <int 0-100, how well it demonstrates measurable impact>,
    "weak_bullets": [{"line": "<exact quoted line>", "why_weak": "<reason>", "improved_version": "<rewrite>"}],
    "missing_impact_keywords": [<skills/keywords a strong candidate in this field would be expected to have but this resume lacks>],
    "overall_feedback": "<2-3 sentence summary of the resume's overall quality and biggest opportunity for improvement>"
  }
}

Rules:
- Only quote lines that actually appear verbatim in the resume text. Never invent content.
- If a category has no problems, set status to "pass" and issues to an empty list.
- Limit weak_bullets to at most 5 of the weakest examples.
- Be strict but fair — this should reflect what a real ATS parser and recruiter would actually flag.
"""


def _fallback_response(message: str) -> ATSScoreResponse:
    """Used only when the resume text is empty or the AI call fails entirely."""
    breakdown = ATSBreakdown(
        keyword_relevance=0.0, structure=0.0, required_sections=0.0,
        skills_clarity=0.0, experience_quality=0.0, formatting=0.0,
    )
    return ATSScoreResponse(
        score=0,
        breakdown=breakdown,
        missing_sections=ALL_STANDARD_SECTIONS,
        detected_sections=[],
        suggestions=[message],
        categories=[],
        ai_review=None,
    )


def _parse_ai_response(parsed: dict) -> ATSScoreResponse:
    breakdown_raw = parsed.get("breakdown") or {}
    breakdown = ATSBreakdown(
        keyword_relevance=float(breakdown_raw.get("keyword_relevance", 0)),
        structure=float(breakdown_raw.get("structure", 0)),
        required_sections=float(breakdown_raw.get("required_sections", 0)),
        skills_clarity=float(breakdown_raw.get("skills_clarity", 0)),
        experience_quality=float(breakdown_raw.get("experience_quality", 0)),
        formatting=float(breakdown_raw.get("formatting", 0)),
    )

    categories = []
    for cat in parsed.get("categories") or []:
        issues = [
            ATSIssue(message=i.get("message", ""), detail=i.get("detail", ""))
            for i in (cat.get("issues") or [])
        ]
        categories.append(ATSCategory(
            name=cat.get("name", "Unnamed"),
            score_percent=int(cat.get("score_percent", 0)),
            status=cat.get("status", "issues"),
            issues=issues,
        ))

    ai_review = parsed.get("ai_review") or None

    return ATSScoreResponse(
        score=int(parsed.get("score", 0)),
        breakdown=breakdown,
        missing_sections=parsed.get("missing_sections") or [],
        detected_sections=parsed.get("detected_sections") or [],
        suggestions=parsed.get("suggestions") or [],
        categories=categories,
        ai_review=ai_review,
    )


def calculate_ats_score(text: str) -> ATSScoreResponse:
    """LLM-powered ATS compatibility score using OpenAI. One call reads the
    resume like a real recruiter/ATS would and returns the score, breakdown,
    itemized per-line feedback, AND the deeper AI review together — so the
    two halves of the report can never disagree, and it's a single API call.

    Falls back to a safe empty response only if the resume is blank, OpenAI
    isn't configured, or the AI call fails entirely — this keeps the endpoint
    from ever crashing.
    """
    if not text or not text.strip():
        return _fallback_response("The resume appears to be empty. Please upload a PDF with readable text.")

    if not is_openai_configured():
        return _fallback_response(
            "ATS scoring is unavailable — OPENAI_API_KEY is not configured on the server."
        )

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY.strip(), timeout=30.0, max_retries=0)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": ATS_SYSTEM_PROMPT},
                {"role": "user", "content": f"RESUME TEXT:\n\n{text}"},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return _parse_ai_response(parsed)

    except Exception:
        logger.exception("OpenAI ATS scoring failed; returning fallback response")
        return _fallback_response(
            "ATS scoring is temporarily unavailable. Please try again in a moment."
        )