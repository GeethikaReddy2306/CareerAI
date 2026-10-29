from dataclasses import dataclass
from typing import Any, Iterable
import re
from difflib import SequenceMatcher
from pydantic import BaseModel, Field
from app.schemas.interview import InterviewQuestionItem
from app.schemas.skill_gap import SkillGapResponse
from app.core.config import settings
from app.services.ai_service import AIStatus, try_structured_ai
from app.services.skill_normalization import normalize_skill, normalize_skills, skill_in_text

CATEGORIES = [
    "Technical",
    "Resume Based",
    "Project Based",
    "Role Specific",
    "Skill Gap Based",
    "Behavioral",
    "HR",
]

_CATEGORY_LOOKUP = {category.casefold(): category for category in CATEGORIES}
_DIFFICULTY_LOOKUP = {level.casefold(): level for level in ("Easy", "Medium", "Hard")}
_TRANSIENT_PROVIDER_STATUSES = {"timeout", "rate_limited", "connection_error", "provider_error"}


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
    failure_category: AIStatus | None = None


@dataclass(frozen=True)
class AnswerEvaluationResult:
    evaluation: "AIAnswerEvaluationSchema | None"
    evaluation_mode: str
    evaluation_notice: str | None = None
    failure_category: AIStatus | None = None


def _as_text(value: Any) -> str:
    return str(value).strip() if value else ""


def _as_text_list(values: Iterable[Any]) -> list[str]:
    return [_as_text(value) for value in values if _as_text(value)]


def _field(value: Any, name: str, default: Any = "") -> Any:
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _dedupe_labels(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        label = _as_text(value)
        if label and label.casefold() not in seen:
            seen.add(label.casefold())
            result.append(label)
    return result


def _role_relevant_profile(
    resume_analysis: dict[str, Any], skill_gap: SkillGapResponse
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return role-relevant skills, project names, gaps, and project facts.

    ``SkillGapResponse`` is based on the selected target role, so its strong
    and intermediate lists are a safer source of technical topics than every
    technology mentioned somewhere in a resume.
    """
    resume_skills = normalize_skills(resume_analysis.get("skills") or [])
    role_evidenced = normalize_skills([*skill_gap.strong, *skill_gap.intermediate])
    role_skill_keys = {skill.casefold() for skill in role_evidenced}
    relevant_skills = [
        skill for skill in resume_skills
        if normalize_skill(skill).casefold() in role_skill_keys
    ]
    gaps = _dedupe_labels([*skill_gap.weak, *skill_gap.missing])

    relevant_project_facts: list[str] = []
    relevant_projects: list[str] = []
    all_project_facts: list[str] = []
    all_project_names: list[str] = []
    for project in resume_analysis.get("projects") or []:
        name = _as_text(_field(project, "name"))
        description = _as_text(_field(project, "description"))
        technologies = _as_text_list(_field(project, "technologies", []) or [])
        fact = " ".join(part for part in (name, description, ", ".join(technologies)) if part)
        if fact:
            all_project_facts.append(fact)
        if name:
            all_project_names.append(name)
        is_relevant = (
            not relevant_skills
            or any(skill_in_text(skill, fact) for skill in relevant_skills)
        )
        if name and is_relevant:
            relevant_projects.append(name)
        if fact and is_relevant:
            relevant_project_facts.append(fact)

    # If the role analysis did not identify any relevant skills, a resume's
    # project evidence is still better than inventing a project. When it did
    # identify role skills, however, do not leak an unrelated project (for
    # example a TypeScript UI project into a Backend Developer interview).
    if not relevant_skills and not relevant_projects:
        relevant_projects = all_project_names
        relevant_project_facts = all_project_facts
    return (
        relevant_skills,
        _dedupe_labels(relevant_projects),
        gaps,
        _dedupe_labels(relevant_project_facts),
    )


def _validated_question_items(
    candidates: Iterable[InterviewQuestionItem],
) -> list[InterviewQuestionItem]:
    """Keep only safe, displayable questions with the public schema's exact values."""
    validated: list[InterviewQuestionItem] = []
    for candidate in candidates:
        question = _as_text(candidate.question)
        topic = _as_text(candidate.topic)
        category = _CATEGORY_LOOKUP.get(_as_text(candidate.category).casefold())
        difficulty = _DIFFICULTY_LOOKUP.get(_as_text(candidate.difficulty).casefold())
        if not category or not difficulty or not topic:
            continue
        # This discards fragments, prompt echoes, and malformed JSON values
        # without trying to transform them into an invented interview question.
        if not (20 <= len(question) <= 700) or "{" in question or "}" in question:
            continue
        validated.append(
            InterviewQuestionItem(
                question=question,
                category=category,
                difficulty=difficulty,
                topic=topic,
            )
        )
    return validated


def _heuristic_interview_questions(
    resume_analysis: dict[str, Any],
    target_role: str,
    skill_gap: SkillGapResponse,
    question_count: int,
) -> AIInterviewQuestionsSchema:
    """Build profile-derived contingency questions when the AI provider is unavailable."""
    skills, projects, gaps, _project_facts = _role_relevant_profile(resume_analysis, skill_gap)
    role_topic = target_role.strip() or "the target role"
    # Do not use unrelated resume skills as a technical topic just to make a
    # longer list. If no role-relevant skill was verified, stay at the role level.
    technical_topics = skills or [role_topic]
    resume_topics = skills or projects or [role_topic]
    project_topics = projects or [role_topic]
    gap_topics = gaps or [role_topic]
    desired = max(question_count * 3, 28)
    questions: list[InterviewQuestionItem] = []

    technical_templates = (
        [
            "Explain the design choices you would make when using {topic} in a {role} system.",
            "How would you diagnose a production failure involving {topic}, from first signal through verification?",
            "Which tests would give you confidence that a {topic} implementation is reliable and maintainable?",
            "Describe a trade-off you would evaluate before introducing {topic} into an existing service.",
        ]
        if skills else [
            "Which technical trade-offs would you evaluate first when building a reliable {role} service?",
            "How would you test and observe a core workflow in a {role} system before release?",
            "How would you diagnose a production failure in a {role} service from first signal through verification?",
            "Describe how you would make a safe technical decision when requirements for a {role} system are incomplete.",
        ]
    )
    templates: dict[str, tuple[list[str], list[str], str]] = {
        "Technical": (technical_templates, technical_topics, "Medium"),
        "Resume Based": (
            [
                "Where in your resume did you apply {topic}, and what measurable outcome did you own?",
                "Walk us through a decision involving {topic} on your resume, including alternatives you rejected.",
                "What would you improve if you revisited the resume experience that used {topic}?",
                "How did you validate that your work with {topic} solved the problem you described on your resume?",
            ], resume_topics, "Medium",
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


def _provider_notice(status: AIStatus, action: str = "question generation") -> str | None:
    messages = {
        "not_configured": (
            f"AI {action} is not configured. Set OPENAI_API_KEY in backend/.env to a valid key, "
            "or explicitly enable profile-based fallback for offline operation."
        ),
        "configuration_error": (
            "OpenAI authentication failed. Replace OPENAI_API_KEY in backend/.env with a valid key "
            "for this project, then restart the backend."
        ),
        "permission_error": "The configured OpenAI project does not have permission to use this operation or model.",
        "timeout": f"AI {action} timed out; a clearly labelled profile-based result was used instead.",
        "rate_limited": f"AI {action} is temporarily rate-limited; a clearly labelled profile-based result was used instead.",
        "quota_exhausted": (
            "OpenAI quota is exhausted for this API key. Add billing/credits, then restart the backend and retry."
        ),
        "connection_error": f"AI provider could not be reached; a clearly labelled profile-based result was used instead.",
        "invalid_request": "The AI request was rejected. Verify OPENAI_MODEL and the request settings.",
        "model_unavailable": "The configured AI model is unavailable to this project. Verify OPENAI_MODEL access.",
        "invalid_output": f"AI returned invalid structured output. The {action} result was not saved; try again.",
        "provider_error": f"AI provider was unavailable; a clearly labelled profile-based result was used instead.",
    }
    return messages.get(status)


def _profile_fallback_allowed(status: AIStatus) -> bool:
    """Allow contingency questions only for a transient outage or explicit offline mode."""
    return status in _TRANSIENT_PROVIDER_STATUSES or (
        status == "not_configured" and settings.INTERVIEW_PROFILE_FALLBACK_ENABLED
    )


def _demo_notice(action: str) -> str:
    """Explain the intentional deterministic path without implying an AI call."""
    label = "Demo evaluation — rule-based." if action == "answer evaluation" else "Demo mode — not AI-generated."
    return (
        f"{label} OpenAI is intentionally skipped because INTERVIEW_DEMO_MODE is enabled. "
        "Set INTERVIEW_DEMO_MODE=false after adding a valid backend OPENAI_API_KEY and restarting the backend."
    )


def generate_interview_questions(
    resume_analysis: dict[str, Any],
    target_role: str,
    skill_gap: SkillGapResponse,
    job_description: str | None = None,
    question_count: int = 15,
    excluded_questions: list[Any] | None = None,
    previous_questions: list[Any] | None = None,
) -> InterviewGenerationResult:
    """Generate validated, role-specific interview questions.

    A provider response is never blended with local contingency questions. This
    makes ``generation_mode`` truthful and prevents a malformed AI result from
    looking like a successful AI-generated interview.
    """
    def fallback():
        return _heuristic_interview_questions(
            resume_analysis, target_role, skill_gap, max(question_count * 3, 28)
        )

    # An explicit demo setting is intentionally checked before the provider
    # call. It produces a repeatable, fast presentation flow while making the
    # source unambiguous in the API response and UI.
    if settings.INTERVIEW_DEMO_MODE:
        demo_questions = _validated_question_items(fallback().questions)
        selected = select_questions_with_category_coverage(
            demo_questions,
            [*(excluded_questions or []), *(previous_questions or [])],
            question_count,
        )
        notice = _demo_notice("question generation")
        if len(selected) < question_count:
            notice += (
                f" Only {len(selected)} unique demo question"
                f"{' was' if len(selected) == 1 else 's were'} available for this request."
            )
        return InterviewGenerationResult(
            questions=selected,
            generation_mode="demo",
            generation_notice=notice,
        )

    relevant_skills, _relevant_projects, gaps, project_facts = _role_relevant_profile(resume_analysis, skill_gap)
    experience_level = _as_text(resume_analysis.get("experience_level")) or "not extracted"
    skills_text = ", ".join(relevant_skills) or "No role-relevant resume skills were verified"
    projects_text = "; ".join(project_facts) or "No project details were extracted"
    jd_context = f"\nTarget Job Description:\n{job_description}" if job_description else ""

    # The public API allows up to 50 requested questions. Ask for a bounded
    # surplus so deduplication can still fulfill large valid requests.
    candidate_count = min(60, max(question_count + 10, 12))
    category_instruction = ", ".join(CATEGORIES[:min(question_count, len(CATEGORIES))])
    prompt = (
        f"Generate {candidate_count} candidate interview questions for a candidate applying for: '{target_role}'.\n"
        f"Candidate experience level: {experience_level}\n"
        f"Verified role-relevant resume skills: {skills_text}\n"
        f"Relevant project evidence: {projects_text}\n"
        f"Verified weak or missing role skills: {', '.join(gaps) or 'None extracted'}{jd_context}\n\n"
        "Ground every technical, resume, and project question in the evidence above. Do not use an unrelated"
        " resume technology as a technical topic unless the job description explicitly makes it relevant.\n"
        f"Cover these categories when enough questions are requested: {category_instruction}.\n"
        f"Allowed categories are exactly: {', '.join(CATEGORIES)}.\n"
        f"For each question, specify: 'question', 'category' (one allowed exact name), "
        f"'difficulty' ('Easy'|'Medium'|'Hard'), 'topic'.\n"
        'Return JSON exactly in this shape: {"questions": [...]}.'
    )

    system_prompt = (
        "You are an expert technical hiring manager and interviewer. You produce realistic, insightful, "
        "personalized interview questions that test real engineering ability rather than memorized trivia."
    )

    hard_exclusions = list(excluded_questions or [])
    soft_exclusions = list(previous_questions or [])
    ai_questions: list[InterviewQuestionItem] = []
    ai_status: AIStatus = "success"

    # Ask for surplus candidates and one focused retry. This retry handles a
    # real-but-short or duplicate-heavy response without switching to templates.
    for attempt in range(2):
        attempt_prompt = prompt
        if attempt:
            attempt_prompt += (
                "\nReturn materially different questions. Avoid these already valid questions:\n"
                + "\n".join(item.question for item in ai_questions[-20:])
            )
        result, ai_status = try_structured_ai(
            prompt=attempt_prompt,
            system_prompt=system_prompt,
            schema_cls=AIInterviewQuestionsSchema,
        )
        if result:
            ai_questions.extend(_validated_question_items(result.questions))
            selected = select_questions_with_category_coverage(
                ai_questions, [*hard_exclusions, *soft_exclusions], question_count
            )
            if len(selected) >= question_count:
                break
        else:
            # Configuration and invalid-output failures should stay visible
            # rather than being disguised as an AI-successful fallback.
            if not _profile_fallback_allowed(ai_status):
                break
            break

    if ai_questions:
        # Keep both session and historic questions as exclusions. Returning a
        # smaller truthful result is better than repeating a question the user
        # has already practiced or padding an AI batch with local templates.
        selected = select_questions_with_category_coverage(
            ai_questions, [*hard_exclusions, *soft_exclusions], question_count
        )
        notice = None
        if ai_status != "success":
            notice = _provider_notice(ai_status)
        if len(selected) < question_count:
            shortage_notice = (
                f"Only {len(selected)} validated unique AI-generated question"
                f"{' was' if len(selected) == 1 else 's were'} available for this request."
            )
            notice = f"{notice} {shortage_notice}" if notice else shortage_notice
        return InterviewGenerationResult(
            questions=selected,
            generation_mode="ai",
            generation_notice=notice,
            failure_category=ai_status if ai_status != "success" else None,
        )

    # A successful transport response with no usable question records is an
    # invalid AI output, not a provider outage eligible for fallback.
    if ai_status == "success":
        ai_status = "invalid_output"

    if _profile_fallback_allowed(ai_status):
        fallback_questions = _validated_question_items(fallback().questions)
        selected = select_questions_with_category_coverage(
            fallback_questions, [*hard_exclusions, *soft_exclusions], question_count
        )
        return InterviewGenerationResult(
            questions=selected,
            generation_mode="profile_based",
            generation_notice=_provider_notice(ai_status),
            failure_category=ai_status,
        )

    return InterviewGenerationResult(
        questions=[],
        generation_mode="error",
        generation_notice=_provider_notice(ai_status) or "AI question generation failed. No questions were saved.",
        failure_category=ai_status,
    )


class AIAnswerEvaluationSchema(BaseModel):
    score: int = Field(default=50, ge=0, le=100)
    verdict: str = Field(default="Adequate")
    feedback: str = Field(default="Provide a more structured answer with a concrete example.")
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)


def _is_valid_ai_evaluation(result: AIAnswerEvaluationSchema) -> bool:
    """Reject partial/default-shaped provider objects before an answer is saved."""
    required_fields = {
        "score",
        "verdict",
        "feedback",
        "strengths",
        "improvements",
        "missing_concepts",
    }
    return (
        required_fields.issubset(result.model_fields_set)
        and result.verdict in {"Strong", "Adequate", "Needs Work"}
        and len(result.feedback.strip()) >= 20
    )


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
) -> AnswerEvaluationResult:
    def fallback():
        return _heuristic_evaluate_answer(question, answer, topic, category)

    if settings.INTERVIEW_DEMO_MODE:
        return AnswerEvaluationResult(
            evaluation=fallback(),
            evaluation_mode="demo",
            evaluation_notice=_demo_notice("answer evaluation"),
        )

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
    result, ai_status = try_structured_ai(
        prompt=prompt,
        system_prompt="You are a supportive but honest interview coach. Score fairly and give actionable feedback.",
        schema_cls=AIAnswerEvaluationSchema,
        temperature=0.3,
    )
    if result and _is_valid_ai_evaluation(result):
        return AnswerEvaluationResult(evaluation=result, evaluation_mode="ai")

    if result:
        ai_status = "invalid_output"
    if _profile_fallback_allowed(ai_status):
        return AnswerEvaluationResult(
            evaluation=fallback(),
            evaluation_mode="profile_based",
            evaluation_notice=_provider_notice(ai_status, "answer evaluation"),
            failure_category=ai_status,
        )
    return AnswerEvaluationResult(
        evaluation=None,
        evaluation_mode="error",
        evaluation_notice=_provider_notice(ai_status, "answer evaluation")
        or "AI answer evaluation failed. The answer was not saved.",
        failure_category=ai_status,
    )

