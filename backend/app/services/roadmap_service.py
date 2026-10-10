from typing import Any
from pydantic import BaseModel, Field
from app.schemas.career_roadmap import RoadmapPhase, RoadmapResponse
from app.schemas.skill_gap import SkillGapResponse
from app.services.ai_service import call_structured_ai


class AIRoadmapSchema(BaseModel):
    roadmap: list[RoadmapPhase] = Field(default_factory=list)


def _heuristic_roadmap(
    target_role: str,
    current_level: str,
    known_skills: list[str],
    gap_skills: list[str],
) -> AIRoadmapSchema:
    """Deterministic fallback roadmap generator that respects candidate's existing skills."""
    phases: list[RoadmapPhase] = []
    phase_num = 1

    # Filter gap skills
    high_priority_gaps = [s for s in gap_skills if s in ["Docker", "Kubernetes", "AWS", "Azure", "GCP", "PostgreSQL", "SQL"]]
    adv_gaps = [s for s in gap_skills if s in ["System Design", "Caching", "Message Queues", "Microservices", "CI/CD"]]
    other_gaps = [s for s in gap_skills if s not in high_priority_gaps and s not in adv_gaps]

    # Phase 1: Infrastructure & Cloud (if needed) or Core Gaps
    p1_skills = high_priority_gaps[:3] or (gap_skills[:2] if gap_skills else ["Docker", "AWS"])
    phases.append(
        RoadmapPhase(
            phase=phase_num,
            title="Containerization & Cloud Infrastructure",
            description=f"Establish robust containerized environments and cloud deployment fundamentals for {target_role}.",
            skills=p1_skills,
            topics=["Docker containerization & multi-stage builds", "Cloud deployment best practices", "Environment isolation"],
            projects=["Dockerize existing backend APIs with PostgreSQL and automated Docker Compose environment"],
            estimated_weeks=3,
            priority="High",
        )
    )
    phase_num += 1

    # Phase 2: Scalability & Distributed Systems
    p2_skills = adv_gaps[:3] or ["System Design", "Caching", "Message Queues"]
    phases.append(
        RoadmapPhase(
            phase=phase_num,
            title="Backend Architecture & Distributed Systems",
            description="Master horizontal scalability, caching strategies, and event-driven architecture.",
            skills=p2_skills,
            topics=["REST API architectural patterns", "In-memory caching with Redis", "Asynchronous messaging with RabbitMQ/Kafka", "Database query indexing"],
            projects=["Architect a high-throughput event processing service with Redis caching and background task queues"],
            estimated_weeks=4,
            priority="High",
        )
    )
    phase_num += 1

    # Phase 3: Production Engineering & Senior Readiness
    p3_skills = other_gaps[:2] or ["CI/CD", "Monitoring", "Production Reliability"]
    phases.append(
        RoadmapPhase(
            phase=phase_num,
            title="Production Engineering & CI/CD Automation",
            description=f"Elevate engineering practices to meet {target_role} production standards.",
            skills=p3_skills,
            topics=["Automated testing & linting workflows", "GitHub Actions CI/CD pipelines", "Observability, health checks, and structured logging"],
            projects=["Implement an end-to-end automated deployment pipeline with GitHub Actions and container registries"],
            estimated_weeks=2,
            priority="Medium",
        )
    )

    return AIRoadmapSchema(roadmap=phases)


def generate_career_roadmap(
    resume_analysis: dict[str, Any],
    target_role: str,
    skill_gap: SkillGapResponse,
) -> list[RoadmapPhase]:
    """Generate a personalized, gap-focused career roadmap avoiding basics the candidate already knows."""
    known_skills = list(dict.fromkeys(skill_gap.strong + skill_gap.intermediate))
    gap_skills = list(dict.fromkeys(skill_gap.missing + skill_gap.weak))
    current_level = resume_analysis.get("experience_level") or "Junior"

    def fallback():
        return _heuristic_roadmap(target_role, current_level, known_skills, gap_skills)

    prompt = (
        f"Generate a personalized, structured learning roadmap for a candidate aiming to become a '{target_role}'.\n\n"
        f"Candidate Current Level: {current_level}\n"
        f"Candidate ALREADY Knows (DO NOT TEACH BASICS OF THESE): {', '.join(known_skills) if known_skills else 'Basic programming'}\n"
        f"Candidate Target Skill Gaps & Weaknesses: {', '.join(gap_skills) if gap_skills else 'Advanced system design, distributed systems'}\n\n"
        f"Generate 3 to 4 chronological phases. Each phase must have: 'phase' (int), 'title' (str), 'description' (str), "
        f"'skills' (list of str), 'topics' (list of str), 'projects' (list of str), 'estimated_weeks' (int), 'priority' ('High'|'Medium'|'Low').\n"
        f"Return JSON: {{'roadmap': [...]}}"
    )

    system_prompt = (
        "You are an elite technical career advisor. You create highly practical, personalized engineering roadmaps. "
        "Never recommend basic intro tutorials for skills the candidate already has master or intermediate experience in."
    )

    ai_result = call_structured_ai(
        prompt=prompt,
        system_prompt=system_prompt,
        schema_cls=AIRoadmapSchema,
        fallback_factory=fallback,
    )

    return ai_result.roadmap if ai_result.roadmap else fallback().roadmap

