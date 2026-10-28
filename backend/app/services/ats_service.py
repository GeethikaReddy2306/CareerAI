"""
ATS scoring service.

Strategy:
  1. If OpenAI is configured and reachable → use it (richer, recruiter-level output).
  2. If OpenAI is unavailable or fails for any reason → deterministic engine runs
     automatically. The feature always returns a real score.
  3. Only truly empty resume text produces a zero-score fallback.
"""
import json
import logging
import math
import re
from collections import Counter

from openai import OpenAI

from app.core.config import settings
from app.schemas.resume_analysis import ATSBreakdown, ATSCategory, ATSImprovement, ATSIssue, ATSScoreResponse
from app.services.ai_service import is_openai_configured

logger = logging.getLogger(__name__)

ALL_STANDARD_SECTIONS = [
    "Contact Information", "Professional Summary", "Skills",
    "Education", "Work Experience", "Projects", "Certifications",
]

# ─── Keyword & pattern data ───────────────────────────────────────────────────

INDUSTRY_KEYWORDS = [
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "perl", "dart",
    # Web / frontend
    "html", "css", "react", "angular", "vue", "next.js", "nuxt", "svelte",
    "tailwind", "bootstrap", "sass", "webpack", "vite", "redux", "jquery",
    "remix", "gatsby", "htmx",
    # Backend / APIs
    "fastapi", "django", "flask", "spring", "express", "node.js", "rails",
    "graphql", "rest", "restful", "grpc", "websocket", "soap",
    # Databases
    "sql", "mysql", "postgresql", "mongodb", "redis", "sqlite", "oracle",
    "cassandra", "dynamodb", "firebase", "elasticsearch", "neo4j", "supabase",
    # Cloud / DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
    "jenkins", "ci/cd", "linux", "bash", "nginx", "cloudflare",
    "github actions", "gitlab ci",
    # MERN / full-stack
    "mern", "mongoose", "express.js",
    # Data / ML / AI
    "pandas", "numpy", "tensorflow", "pytorch", "scikit-learn", "keras",
    "spark", "hadoop", "tableau", "power bi", "machine learning",
    "deep learning", "nlp", "computer vision", "data analysis", "data science",
    "langchain", "openai", "llm",
    # Tools / practices
    "git", "agile", "scrum", "jira", "confluence", "microservices", "api",
    "jwt", "oauth", "testing", "unit testing", "jest", "pytest", "selenium",
    "postman", "figma", "linux", "bash", "shell",
    # Soft / professional
    "leadership", "communication", "collaboration", "problem solving",
    "project management", "analytical", "teamwork",
]

ACTION_VERBS = {
    "developed", "built", "designed", "implemented", "created", "managed",
    "led", "improved", "optimized", "reduced", "increased", "delivered",
    "architected", "deployed", "integrated", "maintained", "analyzed",
    "automated", "collaborated", "coordinated", "established", "enhanced",
    "migrated", "refactored", "streamlined", "launched", "authored",
    "engineered", "spearheaded", "trained", "mentored", "scaled", "owned",
    "drove", "achieved", "resolved", "diagnosed", "configured", "tested",
    "documented", "researched", "presented", "negotiated", "mentored",
}

WEAK_PHRASES = {
    r"\bresponsible for\b": 'Replace "responsible for" with a direct action verb',
    r"\bworked (on|with|in)\b": 'Replace "worked on/with/in" with a specific action verb',
    r"\bhelped\b": 'Replace "helped" with your specific contribution',
    r"\bassisted (with|in)\b": 'Replace "assisted with" with a direct action verb',
    r"\bwas involved in\b": 'Replace vague "was involved in" with your exact role',
}

SECTION_PATTERNS: dict[str, list[str]] = {
    "Contact Information": [
        r"\b(contact|email|phone|linkedin|github|portfolio)\b",
        r"\b[\w.+-]+@[\w-]+\.\w+\b",
        r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
    ],
    "Professional Summary": [
        r"\b(summary|objective|profile|about me|professional summary|career objective|about)\b",
    ],
    "Skills": [
        r"\b(skills|technical skills|technologies|competencies|expertise|tools|stack)\b",
    ],
    "Education": [
        r"\b(education|academic|degree|university|college|bachelor|master|phd|"
        r"diploma|b\.?tech|m\.?tech|b\.?e|m\.?e|school)\b",
    ],
    "Work Experience": [
        r"\b(experience|work history|employment|professional experience|"
        r"work experience|internship|intern|career)\b",
    ],
    "Projects": [
        r"\b(projects?|portfolio|personal projects?|academic projects?|"
        r"side projects?|open.?source)\b",
    ],
    "Certifications": [
        r"\b(certifications?|certificates?|licenses?|credentials?|certified|"
        r"aws certified|google certified|coursera|udemy|hackerrank)\b",
    ],
}

# ─── OpenAI prompt ────────────────────────────────────────────────────────────

ATS_SYSTEM_PROMPT = """\
You are an expert ATS (Applicant Tracking System) resume evaluator and senior technical recruiter.
Analyze the resume text exactly as a real ATS parser + recruiter would.
Output ONLY a valid JSON object matching this EXACT shape:

{
  "score": <int 0-100, overall ATS compatibility>,
  "breakdown": {
    "keyword_relevance": <int 0-100>,
    "structure": <int 0-100>,
    "required_sections": <int 0-100>,
    "skills_clarity": <int 0-100>,
    "experience_quality": <int 0-100>,
    "formatting": <int 0-100>
  },
  "detected_sections": [<subset of the 7 standard sections>],
  "missing_sections": [<the remaining sections not detected>],
  "suggestions": [<3-8 short, specific, actionable improvement suggestions>],
  "categories": [
    {
      "name": "Quantifying Impact",
      "score_percent": <int 0-100>,
      "status": "pass" or "issues",
      "issues": [{"message": "<short label>", "detail": "<exact quoted line from the resume>"}]
    },
    {
      "name": "Repetition",
      "score_percent": <int 0-100>,
      "status": "pass" or "issues",
      "issues": [{"message": "<e.g. 'Developed' used to start 4 bullets>", "detail": "<quoted lines>"}]
    },
    {
      "name": "Spelling & Grammar",
      "score_percent": <int 0-100>,
      "status": "pass" or "issues",
      "issues": [{"message": "<what is wrong>", "detail": "<quoted line + correction>"}]
    },
    {
      "name": "Bullets Consistency",
      "score_percent": <int 0-100>,
      "status": "pass" or "issues",
      "issues": [{"message": "<what is inconsistent>", "detail": "<quoted examples>"}]
    }
  ]
}

Standard sections to check: Contact Information, Professional Summary, Skills,
Education, Work Experience, Projects, Certifications.

Rules:
- Only quote lines that actually appear verbatim in the resume text. Never invent content.
- If a category has no problems, set status to "pass" and issues to an empty list.
- Be strict but fair.
"""

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _kw_in_text(word: str, text: str) -> bool:
    """Word-boundary safe match — 'go' won't match inside 'algorithm'."""
    pattern = r"(?<![A-Za-z0-9])" + re.escape(word) + r"(?![A-Za-z0-9])"
    return bool(re.search(pattern, text, re.IGNORECASE))


_keyword_present = _kw_in_text


def _detect_sections(text: str) -> tuple[list[str], list[str]]:
    detected: list[str] = []
    for section, patterns in SECTION_PATTERNS.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            detected.append(section)
    missing = [s for s in ALL_STANDARD_SECTIONS if s not in detected]
    return detected, missing


# ─── Deterministic sub-scorers (each returns 0-100) ──────────────────────────

def _score_keyword_relevance(text: str) -> float:
    found = sum(1 for kw in INDUSTRY_KEYWORDS if _kw_in_text(kw, text))
    # Smooth curve: ~20 keywords → 100, ~10 → 70, ~5 → 45
    return round(min(100.0, 100.0 * (1.0 - math.exp(-found / 14.0))), 1)


def _score_required_sections(detected: list[str]) -> float:
    return round(len(detected) / len(ALL_STANDARD_SECTIONS) * 100.0, 1)


def _score_structure(text: str, detected: list[str]) -> float:
    score = 0.0
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return 0.0
    # Sections present (40 pts)
    score += min(40.0, len(detected) / 5.0 * 40.0)
    # Bullet points (20 pts)
    bullets = [l for l in lines if l[:1] in "•-*–▪○"]
    score += 20.0 if len(bullets) >= 5 else (10.0 if len(bullets) >= 2 else 0.0)
    # Reasonable length (20 pts)
    score += 20.0 if 30 <= len(lines) <= 160 else (10.0 if 10 <= len(lines) < 30 else 0.0)
    # Clear section headers: short title-case / all-caps lines (20 pts)
    headers = [l for l in lines if len(l) < 50 and (l.isupper() or (l.istitle() and len(l.split()) <= 5))]
    score += 20.0 if len(headers) >= 4 else (10.0 if len(headers) >= 2 else 0.0)
    return round(min(100.0, score), 1)


def _score_skills_clarity(text: str, detected: list[str]) -> float:
    if "Skills" not in detected:
        return 10.0
    score = 40.0  # dedicated section exists
    found_kw = sum(1 for kw in INDUSTRY_KEYWORDS if _kw_in_text(kw, text))
    score += min(40.0, found_kw / 10.0 * 40.0)
    if re.search(r"\b(languages?|frameworks?|tools?|databases?|cloud)\s*:", text, re.IGNORECASE):
        score += 20.0  # categorized skills
    return round(min(100.0, score), 1)


def _score_experience_quality(text: str) -> float:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return 0.0
    # Action verbs starting bullets (50 pts)
    action_count = sum(
        1 for l in lines
        if (l.lstrip("•-*– ").split() or [""])[0].lower() in ACTION_VERBS
    )
    action_score = min(50.0, action_count / 8.0 * 50.0)
    # Quantified impact (50 pts)
    quant_count = sum(
        1 for l in lines
        if re.search(
            r"\b\d+(\.\d+)?(%|x\b|\$|k\b|million|billion|users?|customers?|members?)\b",
            l, re.IGNORECASE
        ) or re.search(
            r"\b(reduced|increased|improved|grew|saved|achieved|delivered)\b.{0,50}\d+",
            l, re.IGNORECASE
        )
    )
    quant_score = min(50.0, quant_count / 5.0 * 50.0)
    return round(action_score + quant_score, 1)


def _score_formatting(text: str) -> float:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return 0.0
    score = 60.0
    # Penalise very long lines (unformatted blobs)
    long_ratio = sum(1 for l in lines if len(l) > 120) / len(lines)
    if long_ratio > 0.3:
        score -= 20.0
    # Penalise excessive ALL-CAPS lines
    caps_count = sum(1 for l in lines if l.isupper() and len(l) > 10)
    if caps_count > 5:
        score -= 10.0
    # Reward bullets
    if any(l[:1] in "•-*–▪" for l in lines):
        score += 15.0
    # Penalise near-empty (single blob)
    if len(lines) < 5:
        score -= 30.0
    # Reward moderate average line length
    avg_len = sum(len(l) for l in lines) / len(lines)
    if 30 <= avg_len <= 80:
        score += 15.0
    return round(max(0.0, min(100.0, score)), 1)


# ─── Category builder ─────────────────────────────────────────────────────────

def _build_categories(text: str) -> list[ATSCategory]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    categories: list[ATSCategory] = []

    # ── Quantifying Impact ────────────────────────────────────────────────────
    unquantified = [
        l for l in lines
        if l[:1] in "•-*–▪"          # is a bullet
        and not re.search(r"\d", l)   # no digit → no measurable outcome
        and len(l) > 20
    ][:3]
    if unquantified:
        qi_issues = [
            ATSIssue(message="No measurable outcome", detail=f'"{l[:100]}"')
            for l in unquantified
        ]
        categories.append(ATSCategory(
            name="Quantifying Impact",
            score_percent=max(0, 100 - len(unquantified) * 25),
            status="issues",
            issues=qi_issues,
        ))
    else:
        categories.append(ATSCategory(
            name="Quantifying Impact", score_percent=85, status="pass", issues=[],
        ))

    # ── Repetition ────────────────────────────────────────────────────────────
    first_words = [
        l.lstrip("•-*– ").split()[0].lower()
        for l in lines
        if l[:1] in "•-*–▪" and l.lstrip("•-*– ").split()
    ]
    verb_counts = Counter(w for w in first_words if w in ACTION_VERBS)
    repeated = [(v, c) for v, c in verb_counts.items() if c >= 3]
    if repeated:
        rep_issues = [
            ATSIssue(
                message=f'"{v.title()}" starts {c} bullets',
                detail="Vary your opening verbs to improve readability and ATS parsing.",
            )
            for v, c in repeated[:3]
        ]
        categories.append(ATSCategory(
            name="Repetition",
            score_percent=max(0, 100 - len(repeated) * 20),
            status="issues",
            issues=rep_issues,
        ))
    else:
        categories.append(ATSCategory(
            name="Repetition", score_percent=90, status="pass", issues=[],
        ))

    # ── Spelling & Grammar (heuristic weak-phrase detection) ─────────────────
    grammar_issues: list[ATSIssue] = []
    for pattern, message in WEAK_PHRASES.items():
        for line in lines:
            if re.search(pattern, line, re.IGNORECASE) and len(line) < 200:
                grammar_issues.append(ATSIssue(message=message, detail=f'"{line[:100]}"'))
                break  # one example per pattern
    if grammar_issues:
        categories.append(ATSCategory(
            name="Spelling & Grammar",
            score_percent=max(30, 100 - len(grammar_issues) * 20),
            status="issues",
            issues=grammar_issues[:3],
        ))
    else:
        categories.append(ATSCategory(
            name="Spelling & Grammar", score_percent=90, status="pass", issues=[],
        ))

    # ── Bullets Consistency ───────────────────────────────────────────────────
    bullet_chars = [l[0] for l in lines if l[:1] in "•-*–▪○"]
    distinct_chars = len(set(bullet_chars))
    if bullet_chars and distinct_chars > 1:
        dominant = Counter(bullet_chars).most_common(1)[0][0]
        odd_ones = [l for l in lines if l[:1] in "•-*–▪○" and l[0] != dominant][:2]
        bc_issues = [ATSIssue(
            message=f"Mixed bullet styles ({distinct_chars} types used)",
            detail=f'"{odd_ones[0][:80]}"' if odd_ones else "Standardise to one bullet character.",
        )]
        categories.append(ATSCategory(
            name="Bullets Consistency",
            score_percent=max(40, 100 - (distinct_chars - 1) * 25),
            status="issues",
            issues=bc_issues,
        ))
    else:
        categories.append(ATSCategory(
            name="Bullets Consistency", score_percent=90, status="pass", issues=[],
        ))

    return categories


def _build_suggestions(
    text: str,
    detected: list[str],
    missing: list[str],
    kw_score: float,
    exp_score: float,
) -> list[str]:
    suggestions: list[str] = []
    if missing:
        suggestions.append(f"Add missing sections: {', '.join(missing[:3])}.")
    if kw_score < 50:
        suggestions.append(
            "Include more industry-relevant keywords (languages, frameworks, tools) "
            "matching your target job description."
        )
    if exp_score < 40:
        suggestions.append(
            "Start bullet points with strong action verbs and quantify impact "
            "with numbers, percentages, or scale (e.g. 'Reduced load time by 40%')."
        )
    if "Professional Summary" not in detected:
        suggestions.append(
            "Add a 2–3 sentence professional summary at the top targeting your desired role."
        )
    if "Certifications" not in detected:
        suggestions.append(
            "List relevant certifications (AWS, Google Cloud, Azure, etc.) to improve ATS match."
        )
    if not re.search(r"\b(github|linkedin|portfolio)\b", text, re.IGNORECASE):
        suggestions.append(
            "Add links to your GitHub, LinkedIn, or portfolio to demonstrate real-world work."
        )
    return suggestions[:6]


def _build_improvements(text: str, detected: list[str], missing: list[str], kw_score: float, exp_score: float) -> list[ATSImprovement]:
    """Return improvements tied directly to the scoring signals in this resume."""
    result: list[ATSImprovement] = []
    if missing:
        sections = ", ".join(missing[:3])
        result.append(ATSImprovement(issue=f"Missing section(s): {sections}", why_it_matters="ATS parsers and recruiters rely on standard sections to find qualifications consistently.", suggested_correction=f"Add a clearly labelled {missing[0]} section with information already supported by your resume.", priority="High"))
    if kw_score < 50:
        result.append(ATSImprovement(issue="Limited recognised technical keyword coverage", why_it_matters="A low keyword relevance component makes it harder to match the resume to a specific job description.", suggested_correction="Add only technologies and tools you genuinely used, grouped under a Skills section and reflected in project or experience bullets.", priority="High"))
    if exp_score < 40:
        result.append(ATSImprovement(issue="Few quantified, action-led achievement bullets", why_it_matters="Concrete outcomes make experience easier for both ATS systems and recruiters to evaluate.", suggested_correction="Rewrite relevant bullets with an action, scope, and measured result (for example, a time, percentage, users, or throughput figure).", priority="High"))
    if "Professional Summary" not in detected:
        result.append(ATSImprovement(issue="No professional summary detected", why_it_matters="A concise summary clarifies the intended role and strongest relevant experience.", suggested_correction="Add a 2–3 sentence summary using your actual target role, experience, and verified skills.", priority="Medium"))
    if not re.search(r"\b(github|linkedin|portfolio)\b", text, re.IGNORECASE):
        result.append(ATSImprovement(issue="No professional portfolio link detected", why_it_matters="A link can help reviewers verify relevant projects beyond the one-page resume.", suggested_correction="Add a current GitHub, LinkedIn, or portfolio URL if you have one.", priority="Low"))
    if not result:
        result.append(ATSImprovement(issue="No major deterministic issues detected", why_it_matters="The tested ATS structure, section coverage, and formatting signals are healthy.", suggested_correction="Tailor keywords and achievement examples to each target job description before applying.", priority="Low"))
    return result[:6]


# ─── Deterministic engine ─────────────────────────────────────────────────────

def _calculate_deterministic_score(text: str) -> ATSScoreResponse:
    """
    Full deterministic ATS scoring — works with zero external dependencies.
    Called automatically whenever OpenAI is unavailable or fails.
    """
    detected, missing = _detect_sections(text)

    kw    = _score_keyword_relevance(text)
    struct = _score_structure(text, detected)
    req   = _score_required_sections(detected)
    skills = _score_skills_clarity(text, detected)
    exp   = _score_experience_quality(text)
    fmt   = _score_formatting(text)

    # Weighted overall (weights sum to 1.0)
    overall = round(
        0.30 * kw +
        0.20 * struct +
        0.15 * req +
        0.15 * skills +
        0.10 * exp +
        0.10 * fmt
    )
    overall = max(0, min(100, overall))

    return ATSScoreResponse(
        score=overall,
        breakdown=ATSBreakdown(
            keyword_relevance=kw,
            structure=struct,
            required_sections=req,
            skills_clarity=skills,
            experience_quality=exp,
            formatting=fmt,
        ),
        detected_sections=detected,
        missing_sections=missing,
        suggestions=_build_suggestions(text, detected, missing, kw, exp),
        improvements=_build_improvements(text, detected, missing, kw, exp),
        analysis_mode="deterministic",
        categories=_build_categories(text),
        ai_review=None,
    )


# ─── OpenAI response parser ───────────────────────────────────────────────────

def _parse_openai_response(parsed: dict) -> ATSScoreResponse:
    bd = parsed.get("breakdown") or {}
    breakdown = ATSBreakdown(
        keyword_relevance=float(bd.get("keyword_relevance", 0)),
        structure=float(bd.get("structure", 0)),
        required_sections=float(bd.get("required_sections", 0)),
        skills_clarity=float(bd.get("skills_clarity", 0)),
        experience_quality=float(bd.get("experience_quality", 0)),
        formatting=float(bd.get("formatting", 0)),
    )
    categories: list[ATSCategory] = []
    for cat in parsed.get("categories") or []:
        issues = [
            ATSIssue(message=i.get("message", ""), detail=i.get("detail", ""))
            for i in (cat.get("issues") or [])
        ]
        categories.append(ATSCategory(
            name=cat.get("name", "Unnamed"),
            score_percent=int(cat.get("score_percent", 0)),
            status=cat.get("status", "issues"),
            issues=issues,
        ))
    return ATSScoreResponse(
        score=int(parsed.get("score", 0)),
        breakdown=breakdown,
        missing_sections=parsed.get("missing_sections") or [],
        detected_sections=parsed.get("detected_sections") or [],
        suggestions=parsed.get("suggestions") or [],
        improvements=[],
        analysis_mode="ai_validated",
        categories=categories,
        ai_review=None,  # populated separately by the router via get_llm_review()
    )


# ─── Empty-text fallback (score=0 only for blank resumes) ────────────────────

def _empty_resume_response() -> ATSScoreResponse:
    return ATSScoreResponse(
        score=0,
        breakdown=ATSBreakdown(
            keyword_relevance=0.0, structure=0.0, required_sections=0.0,
            skills_clarity=0.0, experience_quality=0.0, formatting=0.0,
        ),
        missing_sections=ALL_STANDARD_SECTIONS,
        detected_sections=[],
        suggestions=["The resume appears to be empty. Please upload a PDF with readable text."],
        improvements=[ATSImprovement(issue="No readable resume content", why_it_matters="A score cannot be calculated without extracted text.", suggested_correction="Upload a text-based PDF resume with readable content.", priority="High")],
        categories=[],
        ai_review=None,
    )


# ─── Public API ───────────────────────────────────────────────────────────────

def calculate_ats_score(text: str) -> ATSScoreResponse:
    """
    Calculate an ATS compatibility score for the given resume text.

    - Returns score=0 only if the resume text is empty/blank.
    The score is intentionally deterministic. LLM output is reserved for the
    optional review, so a provider outage cannot make scores or improvements
    inconsistent for identical resumes.
    """
    if not text or not text.strip():
        return _empty_resume_response()

    logger.info("ATS score generated via deterministic engine")
    return _calculate_deterministic_score(text)
