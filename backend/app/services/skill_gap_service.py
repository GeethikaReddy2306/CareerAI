from typing import Any
import re

from pydantic import BaseModel, Field

from app.schemas.skill_gap import PrioritizedSkillItem, SkillGapResponse
from app.services.ai_service import call_structured_ai, is_openai_configured
from app.services.skill_normalization import normalize_skill, normalize_skills, skill_in_text


ROLE_REQUIREMENTS: dict[str, list[str]] = {
    "backend developer": ["Python", "FastAPI", "SQL", "PostgreSQL", "REST APIs", "Docker", "AWS", "Git", "Unit Testing", "System Design"],
    "cloud backend engineer": ["Python", "FastAPI", "SQL", "PostgreSQL", "REST APIs", "Docker", "AWS", "CI/CD", "Git", "System Design"],
    "python developer": ["Python", "FastAPI", "Django", "SQL", "PostgreSQL", "REST APIs", "Docker", "Git", "Unit Testing", "AWS"],
    "frontend developer": ["JavaScript", "TypeScript", "React", "HTML/CSS", "REST APIs", "Git", "Unit Testing"],
    "full stack developer": ["Python", "FastAPI", "JavaScript", "TypeScript", "React", "PostgreSQL", "Docker", "REST APIs", "Git"],
    "devops engineer": ["Linux", "Docker", "Kubernetes", "AWS", "CI/CD", "Git", "Python", "Terraform"],
    "data engineer": ["Python", "SQL", "PostgreSQL", "Docker", "AWS", "Kafka", "Data Modeling", "ETL Pipelines", "Git"],
    "data analyst": ["SQL", "Python", "Data Analysis", "Tableau", "Power BI", "Excel", "Statistics", "Data Visualization"],
    "machine learning engineer": ["Python", "Machine Learning", "SQL", "Docker", "Git", "PyTorch", "TensorFlow", "AWS"],
    "product manager": ["Product Strategy", "User Research", "Analytics", "Roadmapping", "Communication", "Agile"],
}


class AITargetSkillsSchema(BaseModel):
    skills: list[str] = Field(default_factory=list)


def get_target_skills_for_role(target_role: str, user_target_skills: list[str] | None = None) -> list[str]:
    """Return explicit, known, or validated AI role requirements without guessing."""
    if user_target_skills:
        return normalize_skills(user_target_skills)
    role_key = target_role.strip().casefold()
    for role, skills in ROLE_REQUIREMENTS.items():
        if role in role_key or role_key in role:
            return skills.copy()
    if not is_openai_configured():
        raise ValueError("Choose a supported target role or provide target skills; role requirements are unavailable offline.")
    result = call_structured_ai(
        prompt=f"List only the 8-12 core skills required for the professional role '{target_role}'. Return JSON: {{'skills': [...]}}.",
        system_prompt="You are a recruiter. Return concise, industry-standard skill names only.",
        schema_cls=AITargetSkillsSchema,
        fallback_factory=AITargetSkillsSchema,
    )
    skills = normalize_skills(result.skills)
    if not skills:
        raise ValueError("Could not establish role requirements. Provide target skills and try again.")
    return skills


def _field(item: Any, name: str, default: Any = "") -> Any:
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def analyze_skill_gaps(resume_analysis: dict[str, Any], target_role: str, target_skills: list[str] | None = None) -> SkillGapResponse:
    """Classify skills only where a resume has stated or demonstrated evidence."""
    candidate_skills = normalize_skills(resume_analysis.get("skills") or [])
    candidate_keys = {skill.casefold() for skill in candidate_skills}
    projects = resume_analysis.get("projects") or []
    work = resume_analysis.get("work_experience") or []
    evidence = " ".join(
        f"{_field(item, 'name')} {_field(item, 'description')} {' '.join(_field(item, 'technologies', []) or [])}"
        for item in projects
    ) + " " + " ".join(
        f"{_field(item, 'role')} {' '.join(_field(item, 'responsibilities', []) or [])}" for item in work
    )
    profile_text = f"{resume_analysis.get('summary') or ''} {evidence}"
    required = get_target_skills_for_role(target_role, target_skills)
    strong: list[str] = []
    intermediate: list[str] = []
    weak: list[str] = []
    missing: list[str] = []
    prioritized: list[PrioritizedSkillItem] = []
    for skill in required:
        canonical = normalize_skill(skill)
        if canonical.casefold() not in candidate_keys:
            missing.append(canonical)
            prioritized.append(PrioritizedSkillItem(skill=canonical, category="Missing", priority="High", reason=f"Required for {target_role}, but not evidenced in the verified resume skills."))
        elif skill_in_text(canonical, evidence):
            strong.append(canonical)
            prioritized.append(PrioritizedSkillItem(skill=canonical, category="Strong", priority="Low", reason="Listed in the profile and evidenced in a project or work history."))
        elif re.search(rf"\b(basic|beginner|learning|familiar)\b.{{0,40}}\b{re.escape(canonical)}\b|\b{re.escape(canonical)}\b.{{0,40}}\b(basic|beginner|learning|familiar)\b", profile_text, re.I):
            weak.append(canonical)
            prioritized.append(PrioritizedSkillItem(skill=canonical, category="Weak", priority="High", reason="The profile indicates only basic or learning-level familiarity, without practical evidence."))
        else:
            intermediate.append(canonical)
            prioritized.append(PrioritizedSkillItem(skill=canonical, category="Intermediate", priority="Medium", reason="Listed in the profile, but no project or work evidence was extracted."))
    rank = {"High": 0, "Medium": 1, "Low": 2}
    prioritized.sort(key=lambda item: rank[item.priority])
    return SkillGapResponse(target_role=target_role, strong=strong, intermediate=intermediate, weak=weak, missing=missing, prioritized_skills=prioritized)
