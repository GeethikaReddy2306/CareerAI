import re
from typing import Any
from pydantic import BaseModel, Field
from app.services.ai_service import call_structured_ai
from app.services.skill_gap_service import (
    SKILL_NORMALIZATION_MAP,
    normalize_skill,
)

COMMON_TECH_KEYWORDS = [
    "python", "fastapi", "django", "flask", "javascript", "typescript", "react",
    "node.js", "sql", "postgresql", "mysql", "mongodb", "redis", "docker",
    "kubernetes", "aws", "azure", "gcp", "git", "ci/cd", "rest apis", "graphql",
    "microservices", "system design", "caching", "message queues", "kafka",
    "rabbitmq", "unit testing", "pytest", "linux", "agile", "scrum", "cloud",
]


def _safe_get(item: Any, key: str, default: Any = "") -> Any:
    """Helper to safely extract field whether item is a dict or Pydantic model."""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


class AIJobExtractionSchema(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    important_keywords: list[str] = Field(default_factory=list)
    interview_topics: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


def _heuristic_extract_jd(job_description: str) -> AIJobExtractionSchema:
    """Deterministic extractor for job description requirements and technical keywords."""
    lower_jd = job_description.lower()
    found_skills: list[str] = []
    found_keywords: list[str] = []

    for kw in COMMON_TECH_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lower_jd):
            norm = normalize_skill(kw)
            if norm not in found_skills:
                found_skills.append(norm)
            if norm not in found_keywords:
                found_keywords.append(norm)

    # If no specific skills detected, extract capitalized phrases
    if not found_skills:
        found_skills = ["Python", "FastAPI", "SQL", "Docker"]
        found_keywords = ["REST APIs", "Database", "Backend Architecture"]

    return AIJobExtractionSchema(
        required_skills=found_skills,
        important_keywords=found_keywords[:6],
        interview_topics=[f"{s} Architecture & Practices" for s in found_skills[:4]],
        recommendations=[
            f"Build hands-on projects emphasizing {s}" for s in found_skills if s in ["Docker", "AWS", "Kubernetes", "PostgreSQL"]
        ] or ["Prepare system design and API performance optimization examples."],
    )


def analyze_job_description(
    resume_analysis: dict[str, Any],
    job_description: str,
) -> dict[str, Any]:
    """Perform deterministic and semantic Resume vs Job Description comparison."""
    lower_jd = job_description.lower()

    # 1. Extract requirements from JD via AI with heuristic fallback
    def fallback():
        return _heuristic_extract_jd(job_description)

    ai_jd = call_structured_ai(
        prompt=(
            f"Analyze this job description and extract required skills, key technical keywords, "
            f"recommended interview topics, and candidate preparation recommendations.\n\n"
            f"Job Description:\n{job_description}\n\n"
            f"Return JSON conforming to: {{'required_skills': [...], 'important_keywords': [...], 'interview_topics': [...], 'recommendations': [...]}}"
        ),
        system_prompt="You are a senior technical recruiter analyzing job descriptions for candidate matching.",
        schema_cls=AIJobExtractionSchema,
        fallback_factory=fallback,
    )

    jd_skills = [normalize_skill(s) for s in ai_jd.required_skills]
    # Deduplicate while preserving order
    jd_skills = list(dict.fromkeys(jd_skills))

    candidate_skills = [normalize_skill(s) for s in (resume_analysis.get("skills") or [])]
    candidate_skills_lower = {s.lower(): s for s in candidate_skills}

    # Inspect candidate project and work experience context for evidence
    proj_lines = []
    for p in (resume_analysis.get("projects") or []):
        name = _safe_get(p, "name", "")
        desc = _safe_get(p, "description", "")
        techs = _safe_get(p, "technologies", [])
        tech_str = " ".join(techs) if isinstance(techs, list) else str(techs)
        proj_lines.append(f"{name} {desc} {tech_str}")

    exp_lines = []
    for w in (resume_analysis.get("work_experience") or []):
        company = _safe_get(w, "company", "")
        role = _safe_get(w, "role", "")
        resps = _safe_get(w, "responsibilities", [])
        resp_str = " ".join(resps) if isinstance(resps, list) else str(resps)
        exp_lines.append(f"{company} {role} {resp_str}")

    candidate_context = " ".join([
        resume_analysis.get("summary") or "",
        " ".join(proj_lines),
        " ".join(exp_lines),
    ]).lower()

    matched_skills: list[str] = []
    partial_skills: list[str] = []
    missing_skills: list[str] = []

    for req_skill in jd_skills:
        req_lower = req_skill.lower()
        if req_lower in candidate_skills_lower:
            # Check how deeply candidate used it in projects/experience
            mentions = len(re.findall(rf"\b{re.escape(req_lower)}\b", candidate_context))
            is_advanced_in_jd = bool(re.search(rf"\b(advanced|expert|lead|architect|5\+\s*years)\b[^\n]*\b{re.escape(req_lower)}\b", lower_jd))
            if is_advanced_in_jd and mentions < 2:
                partial_skills.append(req_skill)
            else:
                matched_skills.append(req_skill)
        else:
            missing_skills.append(req_skill)

    # If all skills ended up missing or empty, ensure at least primary matched candidate skills are considered
    if not matched_skills and not partial_skills:
        for cs in candidate_skills:
            if cs.lower() in lower_jd:
                matched_skills.append(cs)

    # 2. Meaningful multi-factor scoring calculation (0-100)
    total_req_count = max(len(jd_skills), 1)
    # Skill match score (50% weight): Matched = 100%, Partial = 50%, Missing = 0%
    skill_score = ((len(matched_skills) * 1.0 + len(partial_skills) * 0.5) / total_req_count) * 100
    skill_score = min(skill_score, 100.0)

    # Keyword overlap score (25% weight)
    candidate_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", candidate_context))
    jd_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", lower_jd))
    keyword_overlap = len(candidate_words.intersection(jd_words))
    keyword_score = min((keyword_overlap / max(len(jd_words) * 0.3, 1)) * 100, 100.0)

    # Experience relevance score (25% weight)
    exp_score = 75.0
    cand_level = (resume_analysis.get("experience_level") or "Fresher").lower()
    if "senior" in lower_jd or "lead" in lower_jd:
        exp_score = 90.0 if "senior" in cand_level or "mid" in cand_level else 55.0
    elif "mid" in lower_jd or "3+" in lower_jd:
        exp_score = 85.0 if "mid" in cand_level or "senior" in cand_level else 65.0
    elif "junior" in lower_jd or "entry" in lower_jd or "fresher" in lower_jd:
        exp_score = 90.0

    match_score = int(round(0.50 * skill_score + 0.25 * keyword_score + 0.25 * exp_score))
    match_score = max(0, min(100, match_score))

    # Tailor interview topics
    topics = list(dict.fromkeys(ai_jd.interview_topics + [f"{s} Implementation" for s in matched_skills[:3]]))
    if not topics:
        topics = ["FastAPI Architecture", "REST API Design", "PostgreSQL Optimization", "Docker Deployment"]

    # Recommendations
    recs = list(dict.fromkeys(ai_jd.recommendations))
    if missing_skills:
        recs.insert(0, f"Gain practical experience with missing required skills: {', '.join(missing_skills[:3])}")
    if partial_skills:
        recs.append(f"Deepen project evidence for {', '.join(partial_skills[:2])} with production metrics")

    important_keywords = list(dict.fromkeys(ai_jd.important_keywords or jd_skills[:5]))

    return {
        "match_score": match_score,
        "matched_skills": matched_skills,
        "partial_skills": partial_skills,
        "missing_skills": missing_skills,
        "important_keywords": important_keywords,
        "interview_topics": topics[:6],
        "recommendations": recs[:5],
    }

