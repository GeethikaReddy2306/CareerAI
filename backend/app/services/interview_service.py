from typing import Any
from pydantic import BaseModel, Field
from app.schemas.interview import InterviewQuestionItem
from app.schemas.skill_gap import SkillGapResponse
from app.services.ai_service import call_structured_ai

CATEGORIES = [
    "Technical",
    "Resume Based",
    "Project Based",
    "Role Specific",
    "Skill Gap Based",
    "Behavioral",
    "HR",
]


class AIInterviewQuestionsSchema(BaseModel):
    questions: list[InterviewQuestionItem] = Field(default_factory=list)


def _heuristic_interview_questions(
    resume_analysis: dict[str, Any],
    target_role: str,
    skill_gap: SkillGapResponse,
    question_count: int,
) -> AIInterviewQuestionsSchema:
    """Deterministic fallback question generator covering all 7 categories personalized to the candidate."""
    primary_skills = resume_analysis.get("skills") or ["Python", "FastAPI", "SQL"]
    primary_skill = primary_skills[0] if primary_skills else "Python"
    secondary_skill = primary_skills[1] if len(primary_skills) > 1 else "FastAPI"

    projects = resume_analysis.get("projects") or []
    project_name = projects[0].get("name", "your core project") if projects else "your recent backend project"

    missing_skill = skill_gap.missing[0] if skill_gap.missing else "Docker"
    weak_skill = skill_gap.weak[0] if skill_gap.weak else "System Design"

    curated: list[InterviewQuestionItem] = [
        # 1. Technical
        InterviewQuestionItem(
            question=f"How does concurrency and async/await work under the hood in {primary_skill}?",
            category="Technical",
            difficulty="Medium",
            topic=primary_skill,
        ),
        InterviewQuestionItem(
            question=f"Explain how dependency injection and database session management are handled in {secondary_skill}.",
            category="Technical",
            difficulty="Medium",
            topic=secondary_skill,
        ),
        # 2. Resume Based
        InterviewQuestionItem(
            question=f"Your resume highlights experience with {', '.join(primary_skills[:3])}. Can you walk through how you structured the data layer for performance?",
            category="Resume Based",
            difficulty="Medium",
            topic="Resume Architecture",
        ),
        InterviewQuestionItem(
            question="In your resume you noted performance optimization and indexing. What profiling tools or query explain plans did you use?",
            category="Resume Based",
            difficulty="Hard",
            topic="Performance Optimization",
        ),
        # 3. Project Based
        InterviewQuestionItem(
            question=f"Walk me through the system architecture of '{project_name}'. What were the biggest technical hurdles you overcame?",
            category="Project Based",
            difficulty="Medium",
            topic=project_name,
        ),
        InterviewQuestionItem(
            question=f"If traffic for '{project_name}' increased by 50x overnight, where would the primary bottlenecks occur and how would you scale it?",
            category="Project Based",
            difficulty="Hard",
            topic="Project Scalability",
        ),
        # 4. Role Specific
        InterviewQuestionItem(
            question=f"As a {target_role}, how do you ensure API idempotency and handle distributed transactions across services?",
            category="Role Specific",
            difficulty="Hard",
            topic=f"{target_role} Architecture",
        ),
        InterviewQuestionItem(
            question=f"What strategies do you use for error handling, rate limiting, and defensive validation in modern {target_role} environments?",
            category="Role Specific",
            difficulty="Medium",
            topic="Defensive Engineering",
        ),
        # 5. Skill Gap Based
        InterviewQuestionItem(
            question=f"We noticed that {missing_skill} is essential for this role. How have you approached containerizing or deploying applications in the past, and how quickly can you ramp up on {missing_skill}?",
            category="Skill Gap Based",
            difficulty="Medium",
            topic=missing_skill,
        ),
        InterviewQuestionItem(
            question=f"How would you approach designing a caching layer using {weak_skill} to mitigate database bottlenecks?",
            category="Skill Gap Based",
            difficulty="Medium",
            topic=weak_skill,
        ),
        # 6. Behavioral
        InterviewQuestionItem(
            question="Describe a situation where you had a disagreement with a peer or lead on a technical approach. How did you resolve it?",
            category="Behavioral",
            difficulty="Medium",
            topic="Collaboration & Conflict Resolution",
        ),
        InterviewQuestionItem(
            question="Tell me about a critical production bug or outage you were involved with. What was your triage process and how did you prevent recurrence?",
            category="Behavioral",
            difficulty="Medium",
            topic="Production Incident Response",
        ),
        # 7. HR
        InterviewQuestionItem(
            question="Can you give a brief walkthrough of your background, key strengths, and what drives you as an engineer?",
            category="HR",
            difficulty="Easy",
            topic="Introduction & Career Story",
        ),
        InterviewQuestionItem(
            question=f"What specific aspects of working as a {target_role} align with your long-term career goals?",
            category="HR",
            difficulty="Easy",
            topic="Role Motivation",
        ),
    ]

    # If user requested more questions, cycle or supplement with deeper questions
    while len(curated) < question_count:
        idx = len(curated) + 1
        cat = CATEGORIES[idx % len(CATEGORIES)]
        curated.append(
            InterviewQuestionItem(
                question=f"Advanced {target_role} interview scenario #{idx}: How do you approach testing, linting, and maintaining zero-downtime releases?",
                category=cat,
                difficulty="Medium" if idx % 2 == 0 else "Hard",
                topic=f"{target_role} Best Practices",
            )
        )

    return AIInterviewQuestionsSchema(questions=curated[:question_count])


def generate_interview_questions(
    resume_analysis: dict[str, Any],
    target_role: str,
    skill_gap: SkillGapResponse,
    job_description: str | None = None,
    question_count: int = 15,
) -> list[InterviewQuestionItem]:
    """Generate categorized, personalized interview questions."""
    def fallback():
        return _heuristic_interview_questions(
            resume_analysis, target_role, skill_gap, question_count
        )

    skills_text = ", ".join(resume_analysis.get("skills") or [])
    projects_text = "; ".join(
        [f"{p.get('name', '')} ({', '.join(p.get('technologies', []))}): {p.get('description', '')}" for p in (resume_analysis.get("projects") or [])]
    )
    jd_context = f"\nTarget Job Description:\n{job_description}" if job_description else ""

    prompt = (
        f"Generate {question_count} personalized interview questions for a candidate applying for: '{target_role}'.\n"
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

    ai_result = call_structured_ai(
        prompt=prompt,
        system_prompt=system_prompt,
        schema_cls=AIInterviewQuestionsSchema,
        fallback_factory=fallback,
    )

    questions = ai_result.questions if ai_result.questions else fallback().questions

    # Ensure all 7 categories exist; if any category is missing in AI output, fill from fallback
    existing_cats = {q.category for q in questions}
    fallback_questions = fallback().questions
    for fq in fallback_questions:
        if fq.category not in existing_cats and len(questions) < question_count:
            questions.append(fq)
            existing_cats.add(fq.category)

    return questions[:question_count]


class AIAnswerEvaluationSchema(BaseModel):
    score: int = Field(default=50, ge=0, le=100)
    verdict: str = Field(default="Adequate")
    feedback: str = Field(default="Provide a more structured answer with a concrete example.")
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)


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
    if word_count >= 40:
        strengths.append("Answer has enough depth to be evaluated.")
    else:
        improvements.append("Expand the answer with a real example from your experience.")
    if overlap:
        strengths.append(f"Touched on relevant terms for {topic}.")
    else:
        improvements.append(f"Name specific concepts related to {topic}.")
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
        "feedback (2-4 sentences), strengths (array of short strings), improvements (array of short strings)."
    )
    return call_structured_ai(
        prompt=prompt,
        system_prompt="You are a supportive but honest interview coach. Score fairly and give actionable feedback.",
        schema_cls=AIAnswerEvaluationSchema,
        fallback_factory=fallback,
        temperature=0.3,
    )

