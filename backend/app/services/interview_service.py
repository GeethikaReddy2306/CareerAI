from dataclasses import dataclass
from typing import Any, Iterable
import re
from difflib import SequenceMatcher
from pydantic import BaseModel, Field
from app.schemas.interview import InterviewQuestionItem
from app.schemas.skill_gap import SkillGapResponse
from app.services.ai_service import AIStatus, call_structured_ai, try_structured_ai

CATEGORIES = [
    "Technical",
    "Resume Based",
    "Project Based",
    "Role Specific",
    "Skill Gap Based",
    "Behavioral",
    "HR",
]


def normalize_question(question: str) -> str:
    """Canonical form for exact and near-duplicate question detection."""
    return " ".join(re.findall(r"[a-z0-9]+", (question or "").casefold()))


def _question_value(value: Any) -> tuple[str, str | None]:
    if isinstance(value, InterviewQuestionItem):
        return value.question, value.category
    if isinstance(value, dict):
        return str(value.get("question", "")), value.get("category")
    return str(value or ""), None


def is_duplicate_question(
    question: str,
    existing: Iterable[Any],
    threshold: float = 0.93,
    category: str | None = None,
) -> bool:
    """Reject exact duplicates everywhere and near duplicates within a category.

    Category-aware similarity avoids rejecting a valid behavioral and technical
    question merely because both use broad words such as "project" or "role".
    """
    candidate = normalize_question(question)
    if not candidate:
        return True
    for previous in existing:
        previous_question, previous_category = _question_value(previous)
        normal = normalize_question(previous_question)
        if candidate == normal:
            return True
        if category and previous_category and category != previous_category:
            continue
        if SequenceMatcher(None, candidate, normal).ratio() >= threshold:
            return True
    return False


def unique_questions(
    candidates: Iterable[InterviewQuestionItem], excluded: Iterable[Any], limit: int
) -> list[InterviewQuestionItem]:
    selected: list[InterviewQuestionItem] = []
    seen = list(excluded)
    for candidate in candidates:
        if not is_duplicate_question(candidate.question, seen, category=candidate.category):
            selected.append(candidate)
            seen.append(candidate)
            if len(selected) == limit:
                break
    return selected


def select_questions_with_category_coverage(
    candidates: Iterable[InterviewQuestionItem], excluded: Iterable[Any], limit: int
) -> list[InterviewQuestionItem]:
    """Prefer one valid question per category before filling the remaining slots."""
    candidate_list = list(candidates)
    selected: list[InterviewQuestionItem] = []
    seen = list(excluded)
    for category in CATEGORIES[:min(limit, len(CATEGORIES))]:
        for candidate in candidate_list:
            if candidate.category != category:
                continue
            if not is_duplicate_question(candidate.question, seen, category=candidate.category):
                selected.append(candidate)
                seen.append(candidate)
                break
    for candidate in candidate_list:
        if len(selected) >= limit:
            break
        if not is_duplicate_question(candidate.question, seen, category=candidate.category):
            selected.append(candidate)
            seen.append(candidate)
    return selected


class AIInterviewQuestionsSchema(BaseModel):
    questions: list[InterviewQuestionItem] = Field(default_factory=list)


@dataclass(frozen=True)
class InterviewGenerationResult:
    questions: list[InterviewQuestionItem]
    generation_mode: str
    generation_notice: str | None = None


def _as_text(value: Any) -> str:
    return str(value).strip() if value else ""


def _heuristic_interview_questions(
    resume_analysis: dict[str, Any],
    target_role: str,
    skill_gap: SkillGapResponse,
    question_count: int,
) -> AIInterviewQuestionsSchema:
    """Build varied questions from the candidate's actual profile, not canned data."""
    skills = [_as_text(skill) for skill in (resume_analysis.get("skills") or []) if _as_text(skill)]
    projects = [
        _as_text(project.get("name") if isinstance(project, dict) else getattr(project, "name", ""))
        for project in (resume_analysis.get("projects") or [])
    ]
    projects = [project for project in projects if project]
    gaps = [*_as_text_list(skill_gap.missing), *_as_text_list(skill_gap.weak)]
    role_topic = target_role.strip() or "the target role"
    technical_topics = skills or [role_topic]
    project_topics = projects or [role_topic]
    gap_topics = gaps or [role_topic]
    desired = max(question_count * 3, 28)
    questions: list[InterviewQuestionItem] = []

    templates: dict[str, tuple[list[str], list[str], str]] = {
        "Technical": (
            [
                "Explain the design choices you would make when using {topic} in a {role} system.",
                "How would you diagnose a production failure involving {topic}, from first signal through verification?",
                "Which tests would give you confidence that a {topic} implementation is reliable and maintainable?",
                "Describe a trade-off you would evaluate before introducing {topic} into an existing service.",
            ], technical_topics, "Medium",
        ),
        "Resume Based": (
            [
                "Where in your resume did you apply {topic}, and what measurable outcome did you own?",
                "Walk us through a decision involving {topic} on your resume, including alternatives you rejected.",
                "What would you improve if you revisited the resume experience that used {topic}?",
                "How did you validate that your work with {topic} solved the problem you described on your resume?",
            ], technical_topics, "Medium",
        ),
        "Project Based": (
            [
                "Walk through the architecture of {topic}; what was the highest-impact technical decision?",
                "If usage of {topic} grew tenfold, what would you measure first and how would you scale it?",
                "What failure mode in {topic} was hardest to anticipate, and how did you address it?",
                "How did you divide, test, and deliver work for {topic} with other contributors?",
            ], project_topics, "Hard",
        ),
        "Role Specific": (
            [
                "As a {role}, how would you turn an ambiguous requirement into a safe technical delivery plan?",
                "What signals would tell you that a {role} solution is ready to release and operate?",
                "Describe how you would balance speed, quality, and risk when prioritizing work as a {role}.",
                "How would you communicate a technical trade-off to non-specialist stakeholders in a {role} role?",
            ], [role_topic], "Medium",
        ),
        "Skill Gap Based": (
            [
                "What is your plan to close the gap in {topic}, and how would you prove practical competence?",
                "How would you apply {topic} to a realistic problem for this {role} position?",
                "Which fundamentals of {topic} would you learn first before taking ownership in production?",
                "Describe a small project or experiment that would demonstrate readiness in {topic}.",
            ], gap_topics, "Medium",
        ),
        "Behavioral": (
            [
                "Tell me about a time you had to resolve a disagreement about a technical approach. What was the result?",
                "Describe a difficult delivery or incident. How did you organize the response and prevent recurrence?",
                "Give an example of feedback that changed how you work with a team.",
                "Tell me about a time you had to explain a complex decision clearly under time pressure.",
            ], [role_topic], "Medium",
        ),
        "HR": (
            [
                "How does this {role} opportunity connect to the direction you want your career to take?",
                "Which strengths from your background would you bring first to a {role} team?",
                "What kind of team environment helps you do your best work as a {role}?",
                "What would success in your first few months as a {role} look like to you?",
            ], [role_topic], "Easy",
        ),
    }
    for index in range(desired):
        category = CATEGORIES[index % len(CATEGORIES)]
        variants, topics, difficulty = templates[category]
        topic = topics[(index // len(CATEGORIES)) % len(topics)]
        question = variants[(index // (len(CATEGORIES) * max(len(topics), 1))) % len(variants)].format(
            topic=topic, role=role_topic
        )
        questions.append(InterviewQuestionItem(question=question, category=category, difficulty=difficulty, topic=topic))
    return AIInterviewQuestionsSchema(questions=questions)


def _as_text_list(values: Iterable[Any]) -> list[str]:
    return [_as_text(value) for value in values if _as_text(value)]


def _generation_notice(status: AIStatus) -> str | None:
    messages = {
        "not_configured": "AI provider is not configured; profile-based questions were generated instead.",
        "configuration_error": "AI provider configuration was rejected; profile-based questions were generated instead.",
        "timeout": "AI generation timed out; profile-based questions were generated instead.",
        "rate_limited": "AI generation is temporarily rate-limited; profile-based questions were generated instead.",
        "invalid_output": "AI returned invalid structured output; profile-based questions were generated instead.",
        "provider_error": "AI provider was unavailable; profile-based questions were generated instead.",
    }
    return messages.get(status)


def generate_interview_questions(
    resume_analysis: dict[str, Any],
    target_role: str,
    skill_gap: SkillGapResponse,
    job_description: str | None = None,
    question_count: int = 15,
    excluded_questions: list[Any] | None = None,
    previous_questions: list[Any] | None = None,
) -> InterviewGenerationResult:
    """Generate categorized, personalized interview questions."""
    def fallback():
        return _heuristic_interview_questions(
            resume_analysis, target_role, skill_gap, max(question_count * 3, 28)
        )

    skills_text = ", ".join(resume_analysis.get("skills") or [])
    projects_text = "; ".join(
        [f"{p.get('name', '')} ({', '.join(p.get('technologies', []))}): {p.get('description', '')}" for p in (resume_analysis.get("projects") or [])]
    )
    jd_context = f"\nTarget Job Description:\n{job_description}" if job_description else ""

    candidate_count = min(50, max(question_count * 3, 21))
    prompt = (
        f"Generate {candidate_count} candidate interview questions for a candidate applying for: '{target_role}'.\n"
        f"Candidate Resume Skills: {skills_text}\n"
        f"Candidate Projects: {projects_text}\n"
        f"Candidate Missing Skills / Gaps: {', '.join(skill_gap.missing)}\n"
        f"Candidate Weak Skills: {', '.join(skill_gap.weak)}{jd_context}\n\n"
        f"You MUST include questions from each of the following 7 categories:\n"
        f"1. Technical (candidate's actual skills)\n"
        f"2. Resume Based (technologies & experience listed in resume)\n"
        f"3. Project Based (deep dive on candidate's listed projects)\n"
        f"4. Role Specific (requirements of '{target_role}')\n"
        f"5. Skill Gap Based (probing weak/missing skills)\n"
        f"6. Behavioral (teamwork, challenges, deadlines)\n"
        f"7. HR (Tell me about yourself, motivations)\n\n"
        f"For each question, specify: 'question', 'category' (one of the 7 exact names), "
        f"'difficulty' ('Easy'|'Medium'|'Hard'), 'topic'.\n"
        f"Return JSON: {{'questions': [...]}}"
    )

    system_prompt = (
        "You are an expert technical hiring manager and interviewer. You produce realistic, insightful, "
        "personalized interview questions that test real engineering ability rather than memorized trivia."
    )

    hard_exclusions = list(excluded_questions or [])
    soft_exclusions = list(previous_questions or [])
    ai_questions: list[InterviewQuestionItem] = []
    ai_status: AIStatus = "success"

    # Ask for surplus candidates. A second attempt is only made when the first
    # valid AI batch cannot fill the request after duplicate filtering.
    for attempt in range(2):
        attempt_prompt = prompt
        if attempt:
            attempt_prompt += "\nReturn materially different questions and avoid repeating these themes:\n" + "\n".join(
                item.question for item in ai_questions[-20:]
            )
        result, ai_status = try_structured_ai(
            prompt=attempt_prompt,
            system_prompt=system_prompt,
            schema_cls=AIInterviewQuestionsSchema,
        )
        if result:
            ai_questions.extend(result.questions)
            if len(select_questions_with_category_coverage(ai_questions, [*hard_exclusions, *soft_exclusions], question_count)) >= question_count:
                break
        else:
            break

    fallback_questions = fallback().questions
    candidates = [*ai_questions, *fallback_questions]
    # Prefer questions unseen in prior sessions, but never make old history
    # turn a valid request into a failure. Current-session exclusions stay hard.
    selected = select_questions_with_category_coverage(candidates, [*hard_exclusions, *soft_exclusions], question_count)
    if len(selected) < question_count:
        selected = select_questions_with_category_coverage(candidates, hard_exclusions, question_count)

    generation_mode = "ai" if ai_questions else "profile_based"
    notice = _generation_notice(ai_status) if not ai_questions else None
    return InterviewGenerationResult(
        questions=selected,
        generation_mode=generation_mode,
        generation_notice=notice,
    )


class AIAnswerEvaluationSchema(BaseModel):
    score: int = Field(default=50, ge=0, le=100)
    verdict: str = Field(default="Adequate")
    feedback: str = Field(default="Provide a more structured answer with a concrete example.")
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)


def _heuristic_evaluate_answer(question: str, answer: str, topic: str, category: str) -> AIAnswerEvaluationSchema:
    text = (answer or "").strip()
    words = [w for w in text.replace(",", " ").split() if w]
    word_count = len(words)

    haystack = f"{question} {topic} {category}".lower()
    tokens = {w.lower().strip(".,!?") for w in haystack.split() if len(w) > 3}
    overlap = sum(1 for w in {x.lower().strip(".,!?") for x in words} if w in tokens)

    score = 28
    if word_count >= 20:
        score += 18
    if word_count >= 60:
        score += 12
    if word_count >= 120:
        score += 8
    score += min(22, overlap * 4)
    if any(k in text.lower() for k in ("example", "project", "because", "trade-off", "tradeoff", "impact")):
        score += 10
    score = max(8, min(96, score))

    if score >= 75:
        verdict = "Strong"
    elif score >= 50:
        verdict = "Adequate"
    else:
        verdict = "Needs Work"

    strengths: list[str] = []
    improvements: list[str] = []
    missing_concepts: list[str] = []
    if word_count >= 40:
        strengths.append("Answer has enough depth to be evaluated.")
    else:
        improvements.append("Expand the answer with a real example from your experience.")
    if overlap:
        strengths.append(f"Touched on relevant terms for {topic}.")
    else:
        improvements.append(f"Name specific concepts related to {topic}.")
        missing_concepts.append(str(topic))
    if "example" not in text.lower():
        improvements.append("Use the STAR method (Situation, Task, Action, Result) where possible.")
    if not strengths:
        strengths.append("You attempted the question — keep iterating.")

    feedback = (
        f"This {category.lower()} answer scored {score}/100. "
        f"Aim for a structured response that explains the idea, cites {topic}, and closes with a result."
    )
    return AIAnswerEvaluationSchema(
        score=score,
        verdict=verdict,
        feedback=feedback,
        strengths=strengths[:4],
        improvements=improvements[:4],
        missing_concepts=missing_concepts[:4],
    )


def evaluate_mock_answer(
    question: str,
    answer: str,
    category: str = "Technical",
    topic: str = "General",
    target_role: str | None = None,
) -> AIAnswerEvaluationSchema:
    def fallback():
        return _heuristic_evaluate_answer(question, answer, topic, category)

    role_line = f" Target role: {target_role}." if target_role else ""
    prompt = (
        f"Evaluate this mock interview answer.{role_line}\n"
        f"Category: {category}\nTopic: {topic}\n"
        f"Question: {question}\n"
        f"Candidate answer: {answer}\n\n"
        "Return JSON with: score (0-100 integer), verdict (Strong|Adequate|Needs Work), "
        "feedback (2-4 sentences), strengths (array of short strings), improvements (array of short strings), "
        "and missing_concepts (array of concepts the answer should address)."
    )
    return call_structured_ai(
        prompt=prompt,
        system_prompt="You are a supportive but honest interview coach. Score fairly and give actionable feedback.",
        schema_cls=AIAnswerEvaluationSchema,
        fallback_factory=fallback,
        temperature=0.3,
    )

