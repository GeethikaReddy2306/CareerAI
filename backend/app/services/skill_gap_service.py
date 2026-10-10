import re
from typing import Any
from app.schemas.skill_gap import PrioritizedSkillItem, SkillGapResponse
from app.services.ai_service import call_structured_ai
from pydantic import BaseModel, Field

# Common skill normalization mapping
SKILL_NORMALIZATION_MAP: dict[str, str] = {
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "react js": "React",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node js": "Node.js",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "psql": "PostgreSQL",
    "golang": "Go",
    "go lang": "Go",
    "go": "Go",
    "rest": "REST APIs",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "restful": "REST APIs",
    "restful apis": "REST APIs",
    "restful api": "REST APIs",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "docker": "Docker",
    "containerization": "Docker",
    "containers": "Docker",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "spring": "Spring Boot",
    "springboot": "Spring Boot",
    "spring boot": "Spring Boot",
    "graphql": "GraphQL",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "ci / cd": "CI/CD",
    "system design": "System Design",
    "system architecture": "System Design",
    "message queues": "Message Queues",
    "message queue": "Message Queues",
    "rabbitmq": "Message Queues",
    "kafka": "Message Queues",
    "caching": "Caching",
    "redis": "Caching",
    "memcached": "Caching",
    "unit testing": "Unit Testing",
    "unit test": "Unit Testing",
    "pytest": "Unit Testing",
    "git": "Git",
    "github": "Git",
    "version control": "Git",
    "linux": "Linux",
    "unix": "Linux",
    "html": "HTML/CSS",
    "css": "HTML/CSS",
    "html/css": "HTML/CSS",
    "tailwind": "HTML/CSS",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "python": "Python",
    "sql": "SQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "microservices": "Microservices",
}

DEFAULT_ROLE_SKILLS: dict[str, list[str]] = {
    "backend developer": [
        "Python", "FastAPI", "SQL", "PostgreSQL", "REST APIs", "Docker", "AWS", "System Design", "Caching", "Message Queues", "Git"
    ],
    "python developer": [
        "Python", "FastAPI", "Django", "SQL", "PostgreSQL", "REST APIs", "Docker", "Git", "Unit Testing", "AWS"
    ],
    "frontend developer": [
        "JavaScript", "TypeScript", "React", "HTML/CSS", "REST APIs", "Git", "Next.js", "Unit Testing", "State Management"
    ],
    "full stack developer": [
        "Python", "FastAPI", "JavaScript", "TypeScript", "React", "PostgreSQL", "Docker", "REST APIs", "Git", "System Design", "AWS"
    ],
    "devops engineer": [
        "Linux", "Docker", "Kubernetes", "AWS", "CI/CD", "Git", "Python", "System Design", "Monitoring", "Terraform"
    ],
    "data engineer": [
        "Python", "SQL", "PostgreSQL", "Docker", "AWS", "Kafka", "Data Modeling", "ETL Pipelines", "Git"
    ],
    "machine learning engineer": [
        "Python", "Machine Learning", "SQL", "Docker", "Git", "REST APIs", "PyTorch", "TensorFlow", "AWS"
    ],
}


def normalize_skill(skill: str) -> str:
    """Deterministically normalize a skill name."""
    cleaned = skill.strip().lower()
    cleaned = re.sub(r"[\s_]+", " ", cleaned)
    if cleaned in SKILL_NORMALIZATION_MAP:
        return SKILL_NORMALIZATION_MAP[cleaned]
    # Default capitalization
    words = [w.capitalize() for w in skill.strip().split()]
    return " ".join(words)


class AITargetSkillsSchema(BaseModel):
    skills: list[str] = Field(default_factory=list)


def get_target_skills_for_role(target_role: str, user_target_skills: list[str] | None = None) -> list[str]:
    """Retrieve normalized target skills for a given role."""
    if user_target_skills and len(user_target_skills) > 0:
        seen = set()
        result = []
        for s in user_target_skills:
            norm = normalize_skill(s)
            if norm and norm.lower() not in seen:
                seen.add(norm.lower())
                result.append(norm)
        return result

    role_key = target_role.strip().lower()
    for key, skills in DEFAULT_ROLE_SKILLS.items():
        if key in role_key or role_key in key:
            return skills.copy()

    # Fallback using structured AI call or default backend skills
    def fallback():
        return AITargetSkillsSchema(
            skills=[
                "Python", "FastAPI", "SQL", "PostgreSQL", "REST APIs",
                "Docker", "AWS", "System Design", "Caching", "Git"
            ]
        )

    ai_result = call_structured_ai(
        prompt=f"List the top 10 most critical technical skills required for the professional role: '{target_role}'. Return JSON: {{'skills': [...]}}",
        system_prompt="You are a tech recruiter. Return standard, industry-recognized technical skills as JSON.",
        schema_cls=AITargetSkillsSchema,
        fallback_factory=fallback,
    )

    seen = set()
    norm_skills = []
    for s in ai_result.skills:
        n = normalize_skill(s)
        if n and n.lower() not in seen:
            seen.add(n.lower())
            norm_skills.append(n)
    return norm_skills if norm_skills else DEFAULT_ROLE_SKILLS["backend developer"]


def analyze_skill_gaps(
    resume_analysis: dict[str, Any],
    target_role: str,
    target_skills: list[str] | None = None,
) -> SkillGapResponse:
    """Analyze candidate skills against target role requirements and categorize into:

    Strong, Intermediate, Weak, and Missing, with action prioritization.
    """
    candidate_raw_skills = resume_analysis.get("skills") or []
    candidate_norm_map: dict[str, str] = {}
    for s in candidate_raw_skills:
        norm = normalize_skill(s)
        candidate_norm_map[norm.lower()] = norm

    def _safe_val(item: Any, key: str, default: Any = "") -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    # Also inspect projects and experience text for evidence of skill depth
    proj_parts = []
    for p in (resume_analysis.get("projects") or []):
        techs = _safe_val(p, "technologies", [])
        tech_str = " ".join(techs) if isinstance(techs, list) else str(techs)
        proj_parts.append(f"{_safe_val(p, 'name', '')} {_safe_val(p, 'description', '')} {tech_str}")
    project_text = " ".join(proj_parts).lower()

    exp_parts = []
    for w in (resume_analysis.get("work_experience") or []):
        resps = _safe_val(w, "responsibilities", [])
        resp_str = " ".join(resps) if isinstance(resps, list) else str(resps)
        exp_parts.append(f"{_safe_val(w, 'company', '')} {_safe_val(w, 'role', '')} {resp_str}")
    exp_text = " ".join(exp_parts).lower()

    combined_context = f"{project_text} {exp_text}"

    required_skills = get_target_skills_for_role(target_role, target_skills)

    strong: list[str] = []
    intermediate: list[str] = []
    weak: list[str] = []
    missing: list[str] = []
    prioritized_skills: list[PrioritizedSkillItem] = []

    for req in required_skills:
        req_norm = normalize_skill(req)
        req_key = req_norm.lower()

        if req_key in candidate_norm_map:
            # Skill is in candidate's skills list. Check evidence depth in projects/work experience
            occurrences = len(re.findall(rf"\b{re.escape(req_key)}\b", combined_context))
            if occurrences >= 1:
                strong.append(req_norm)
                prioritized_skills.append(
                    PrioritizedSkillItem(
                        skill=req_norm,
                        category="Strong",
                        priority="Low",
                        reason=f"Strong practical experience demonstrated in projects or work history.",
                    )
                )
            else:
                intermediate.append(req_norm)
                prioritized_skills.append(
                    PrioritizedSkillItem(
                        skill=req_norm,
                        category="Intermediate",
                        priority="Medium",
                        reason=f"Demonstrated familiarity in resume, but can be deepened with more complex projects.",
                    )
                )
        else:
            # Skill is completely missing
            missing.append(req_norm)
            prioritized_skills.append(
                PrioritizedSkillItem(
                    skill=req_norm,
                    category="Missing",
                    priority="High",
                    reason=f"Required for {target_role} positions, but not found on the candidate profile.",
                )
            )

    # Sort prioritized skills: High first, then Medium, then Low
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    prioritized_skills.sort(key=lambda x: priority_order.get(x.priority, 3))

    return SkillGapResponse(
        target_role=target_role,
        strong=strong,
        intermediate=intermediate,
        weak=weak,
        missing=missing,
        prioritized_skills=prioritized_skills,
    )

