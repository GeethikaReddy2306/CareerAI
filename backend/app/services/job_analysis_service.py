import re
from typing import Any
from pydantic import BaseModel, Field
from app.services.ai_service import call_structured_ai
from app.services.skill_normalization import normalize_skill, normalize_skills, skill_in_text

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

    jd_skills = normalize_skills(ai_jd.required_skills)
    if not jd_skills:
        raise ValueError("No explicit, supported skill requirements could be extracted from this job description.")

    candidate_skills = [normalize_skill(s) for s in (resume_analysis.get("skills") or []) if normalize_skill(s)]
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

    evidence_lines = [*proj_lines, *exp_lines]
    candidate_context = " ".join([
        resume_analysis.get("summary") or "",
        *evidence_lines,
    ]).lower()

    matched_skills: list[str] = []
    partial_skills: list[str] = []
    missing_skills: list[str] = []

    for req_skill in jd_skills:
        req_lower = req_skill.lower()
        listed_on_resume = req_lower in candidate_skills_lower
        project_or_work_evidence = sum(
            1 for line in evidence_lines if skill_in_text(req_skill, line)
        )
        is_advanced_in_jd = bool(
            re.search(
                rf"\b(advanced|expert(?:ise)?|lead|architect(?:ure)?|[5-9]\+\s*years)\b(?:\W+\w+){{0,5}}\W+{re.escape(req_lower)}\b",
                lower_jd,
            )
        )

        # A partial match requires concrete but incomplete evidence: either the
        # skill appears in project/work material but is not listed as a core
        # skill, or it is listed without enough evidence for a senior demand.
        if listed_on_resume and project_or_work_evidence and (not is_advanced_in_jd or project_or_work_evidence >= 2):
            matched_skills.append(req_skill)
        elif listed_on_resume or project_or_work_evidence:
            partial_skills.append(req_skill)
        else:
            missing_skills.append(req_skill)

    # Keep the score, recommendations, and UI categories a true partition even
    # if a noisy AI extraction returned duplicate or differently-cased skills.
    matched_skills = list(dict.fromkeys(matched_skills))
    partial_skills = [skill for skill in dict.fromkeys(partial_skills) if skill not in matched_skills]
    missing_skills = [
        skill for skill in dict.fromkeys(missing_skills)
        if skill not in matched_skills and skill not in partial_skills
    ]

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
        topics = [f"{skill} implementation" for skill in jd_skills[:4]]

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

