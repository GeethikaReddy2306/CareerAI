from typing import Any

from pydantic import BaseModel, Field

from app.schemas.career_roadmap import RoadmapPhase
from app.schemas.skill_gap import SkillGapResponse
from app.services.ai_service import call_structured_ai
from app.services.skill_normalization import normalize_skills


class AIRoadmapSchema(BaseModel):
    roadmap: list[RoadmapPhase] = Field(default_factory=list)


PREREQUISITE_ORDER = [
    ("foundations", {"Python", "JavaScript", "TypeScript", "SQL", "HTML/CSS", "Linux"}),
    ("application development", {"React", "FastAPI", "Django", "REST APIs", "PostgreSQL", "MongoDB", "Docker"}),
    ("delivery and scale", {"AWS", "GCP", "Azure", "Kubernetes", "CI/CD", "Caching", "Message Queues", "System Design", "Terraform"}),
]


def _phase(index: int, title: str, skills: list[str], target_role: str, priority: str) -> RoadmapPhase:
    skill_text = ", ".join(skills)
    return RoadmapPhase(
        phase=index,
        title=title,
        description=f"Close the {skill_text} gap for {target_role} through applied work. Estimated duration assumes 6–8 focused hours per week.",
        skills=skills,
        topics=[f"Core concepts and trade-offs in {skill}" for skill in skills],
        projects=[f"Extend an existing portfolio project to demonstrate {skill_text}"],
        estimated_weeks=max(2, min(6, len(skills) * 2)),
        priority=priority,
        objectives=[f"Explain when to use {skill} and implement it in a working project" for skill in skills],
        completion_criteria=[f"Commit a reviewed implementation demonstrating {skill}" for skill in skills],
        resource_search_terms=[f"{skill} practical project tutorial" for skill in skills],
    )


def _deterministic_roadmap(target_role: str, skill_gap: SkillGapResponse) -> list[RoadmapPhase]:
    gaps = normalize_skills(skill_gap.missing + skill_gap.weak)
    if not gaps:
        return [RoadmapPhase(
            phase=1, title="Validate role evidence", priority="Low", estimated_weeks=2, skills=[],
            description=f"No unverified skill gaps were found for {target_role}. Strengthen evidence for the target role instead of repeating beginner material. Estimate assumes 6–8 hours per week.",
            topics=["Tailor resume evidence to the target role", "Practice role-specific explanations"],
            projects=["Document measurable outcomes and architecture decisions from an existing project"],
            objectives=["Connect each claimed skill to a concrete project or work example"],
            completion_criteria=["Resume contains role-relevant evidence for every claimed core skill"],
            resource_search_terms=[f"{target_role} portfolio case study examples"],
        )]
    pending = gaps.copy()
    phases: list[RoadmapPhase] = []
    for label, dependencies in PREREQUISITE_ORDER:
        group = [skill for skill in pending if skill in dependencies]
        if group:
            pending = [skill for skill in pending if skill not in group]
            phases.append(_phase(len(phases) + 1, label.title(), group[:3], target_role, "High" if len(phases) == 0 else "Medium"))
    while pending:
        group, pending = pending[:3], pending[3:]
        phases.append(_phase(len(phases) + 1, "Target-role capability", group, target_role, "Medium"))
    return phases


def _validate_roadmap(phases: list[RoadmapPhase], known_skills: list[str], gap_skills: list[str]) -> list[RoadmapPhase]:
    known = {skill.casefold() for skill in known_skills}
    gaps = {skill.casefold() for skill in gap_skills}
    clean: list[RoadmapPhase] = []
    for phase in sorted(phases, key=lambda item: item.phase):
        skills = [skill for skill in normalize_skills(phase.skills) if skill.casefold() not in known and skill.casefold() in gaps]
        if skills:
            clean.append(phase.model_copy(update={"phase": len(clean) + 1, "skills": skills[:3], "estimated_weeks": max(1, phase.estimated_weeks)}))
    return clean


def generate_career_roadmap(resume_analysis: dict[str, Any], target_role: str, skill_gap: SkillGapResponse) -> list[RoadmapPhase]:
    """Create a gap-driven plan; AI prose is accepted only after deterministic validation."""
    known = normalize_skills(skill_gap.strong + skill_gap.intermediate)
    gaps = normalize_skills(skill_gap.missing + skill_gap.weak)
    fallback = lambda: AIRoadmapSchema(roadmap=_deterministic_roadmap(target_role, skill_gap))
    result = call_structured_ai(
        prompt=(f"Create 2-4 ordered roadmap phases for {target_role}. Known skills: {known}. Skill gaps: {gaps}. "
                "Use only gap skills, order prerequisites first, include objectives, completion criteria, resource search terms and estimated weeks. Return JSON {'roadmap': [...]}"),
        system_prompt="You are a career planner. Do not invent resource URLs, credentials, experience, or skills.",
        schema_cls=AIRoadmapSchema, fallback_factory=fallback,
    )
    validated = _validate_roadmap(result.roadmap, known, gaps)
    return validated or _deterministic_roadmap(target_role, skill_gap)
