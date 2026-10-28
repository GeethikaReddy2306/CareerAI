from typing import Any
from app.schemas.career_readiness import CareerReadinessBreakdown, CareerReadinessResponse
from app.schemas.skill_gap import SkillGapResponse


def calculate_career_readiness(
    resume_analysis: dict[str, Any],
    target_role: str,
    skill_gap: SkillGapResponse,
) -> CareerReadinessResponse:
    """Calculate a deterministic, transparent 5-factor career readiness score out of 100."""
    # 1. Skill Match (35% weight)
    total_req_skills = max(
        len(skill_gap.strong) + len(skill_gap.intermediate) + len(skill_gap.weak) + len(skill_gap.missing),
        1,
    )
    weighted_skill_sum = (
        len(skill_gap.strong) * 1.0
        + len(skill_gap.intermediate) * 0.75
        + len(skill_gap.weak) * 0.40
    )
    score_skill_match = round(min((weighted_skill_sum / total_req_skills) * 100, 100.0), 2)

    # 2. Resume Quality (20% weight)
    if resume_analysis.get("ats_score") is not None:
        score_resume_quality = float(resume_analysis["ats_score"])
    else:
        # No ATS assessment exists yet; do not invent a positive quality score.
        score_resume_quality = 0.0

    # 3. Project Experience (15% weight)
    projects = resume_analysis.get("projects") or []
    num_projects = len(projects)
    score_project = 0.0
    if num_projects >= 3:
        score_project += 30.0
    elif num_projects == 2:
        score_project += 20.0
    elif num_projects == 1:
        score_project += 10.0

    # Check if project technologies overlap with strong or target skills
    proj_techs = {
        tech.lower() for p in projects for tech in (p.get("technologies") if isinstance(p, dict) else getattr(p, "technologies", []))
    }
    strong_lower = {s.lower() for s in skill_gap.strong}
    if proj_techs.intersection(strong_lower):
        score_project += 15.0
    score_project = round(min(score_project, 100.0), 2)

    # 4. Interview Readiness (15% weight)
    score_interview = 0.0
    if len(skill_gap.strong) >= 3:
        score_interview += 20.0
    elif len(skill_gap.strong) >= 1:
        score_interview += 10.0

    certs = resume_analysis.get("certifications") or []
    if certs:
        score_interview += 10.0

    if len(skill_gap.missing) <= 2:
        score_interview += 10.0
    elif len(skill_gap.missing) >= 5:
        score_interview -= 10.0
    score_interview = round(max(0.0, min(score_interview, 100.0)), 2)

    # 5. Experience Relevance (15% weight)
    exp_level = (resume_analysis.get("experience_level") or "Fresher").lower()
    target_lower = target_role.lower()

    if "senior" in target_lower or "lead" in target_lower:
        score_exp = 90.0 if "senior" in exp_level else 55.0
    elif "mid" in target_lower:
        score_exp = 85.0 if ("mid" in exp_level or "senior" in exp_level) else 65.0
    else:
        if "senior" in exp_level:
            score_exp = 95.0
        elif "mid" in exp_level:
            score_exp = 90.0
        elif "junior" in exp_level:
            score_exp = 80.0
        else:
            score_exp = 0.0

    work_exps = resume_analysis.get("work_experience") or []
    if work_exps:
        score_exp = min(score_exp + 10.0, 100.0)
    score_exp = round(score_exp, 2)

    # Overall weighted readiness score
    weighted_total = (
        0.35 * score_skill_match
        + 0.20 * score_resume_quality
        + 0.15 * score_project
        + 0.15 * score_interview
        + 0.15 * score_exp
    )
    overall_score = int(round(max(0.0, min(100.0, weighted_total))))

    # Strengths
    strengths = []
    if skill_gap.strong:
        strengths.append(f"Strong proficiency demonstrated in core technologies: {', '.join(skill_gap.strong[:3])}")
    if score_project >= 70:
        strengths.append("Demonstrated project portfolio showcasing practical implementation")
    if score_resume_quality >= 75:
        strengths.append("High ATS structure and resume readability score")
    if not strengths:
        strengths.append("Complete resume analysis and ATS scoring to establish evidence-based strengths")

    # Areas to improve
    areas_to_improve = []
    if skill_gap.missing:
        areas_to_improve.extend(skill_gap.missing[:3])
    if skill_gap.weak:
        areas_to_improve.extend([f"Deepen knowledge in {s}" for s in skill_gap.weak[:2]])
    if score_project < 70:
        areas_to_improve.append("Add more comprehensive production-grade projects")
    if not areas_to_improve:
        areas_to_improve.append("Mock interview practice and advanced system design")

    # Recommendations
    recommendations = []
    if skill_gap.missing:
        recommendations.append(f"Prioritize acquiring hands-on experience in: {', '.join(skill_gap.missing[:2])}")
    if "System Design" in skill_gap.missing or "System Design" in skill_gap.weak:
        recommendations.append("Practice scalable backend system design, caching patterns, and database indexing")
    recommendations.append(f"Build a targeted project focused specifically on {target_role} responsibilities")
    recommendations.append("Participate in mock technical interviews focusing on core architecture and problem-solving")

    breakdown = CareerReadinessBreakdown(
        skill_match=score_skill_match,
        resume_quality=score_resume_quality,
        project_experience=score_project,
        interview_readiness=score_interview,
        experience_relevance=score_exp,
    )

    return CareerReadinessResponse(
        overall_score=overall_score,
        target_role=target_role,
        breakdown=breakdown,
        strengths=list(dict.fromkeys(strengths)),
        areas_to_improve=list(dict.fromkeys(areas_to_improve)),
        recommendations=list(dict.fromkeys(recommendations)),
    )

