import json
import logging
import re
from openai import OpenAI
from app.core.config import settings
from app.schemas.resume_analysis import (
    AIResumeAnalysisResult,
    EducationItem,
    ProjectItem,
    WorkExperienceItem,
)
from app.services.ai_service import is_openai_configured
from app.services.skill_normalization import normalize_skills, skill_in_text

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert technical recruiter and resume analyzer.
Your task is to analyze the candidate's resume text and output a valid JSON object strictly matching this schema:
{
  "summary": "Short professional summary (2-3 sentences)",
  "skills": ["Python", "FastAPI", "PostgreSQL", ...],
  "education": [
    {
      "degree": "Degree title, e.g. B.Tech in Computer Science",
      "institution": "University / College name",
      "year": "Graduation year or date range, e.g. 2024"
    }
  ],
  "projects": [
    {
      "name": "Project name",
      "description": "Short project summary and impact",
      "technologies": ["Python", "Docker"]
    }
  ],
  "certifications": ["AWS Certified Solutions Architect", ...],
  "work_experience": [
    {
      "company": "Company name",
      "role": "Job title",
      "duration": "e.g. Jun 2022 - Aug 2023",
      "responsibilities": ["Key responsibility or achievement"]
    }
  ],
  "strengths": ["Strong backend development fundamentals", "Clean code practices", ...],
  "weaknesses": ["Lack of cloud deployment metrics", ...],
  "experience_level": "Student" | "Fresher" | "Junior" | "Mid-Level" | "Senior",
  "suggested_roles": ["Backend Developer", "Python Developer", "Full Stack Developer"]
}

Be accurate, extract real information present in the resume, and categorize technical and professional skills clearly.
Output ONLY valid JSON.
"""


def _heuristic_resume_analysis(text: str) -> AIResumeAnalysisResult:
    """Fallback heuristic analyzer used when OpenAI API key is unavailable or during offline testing."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lower_text = text.lower()

    # Heuristic skills extraction
    common_skills = [
        "Python", "FastAPI", "Flask", "Django", "JavaScript", "TypeScript", "React",
        "Node.js", "SQL", "PostgreSQL", "MySQL", "MongoDB", "Docker", "Kubernetes",
        "AWS", "Azure", "GCP", "Git", "Linux", "REST API", "GraphQL", "Java", "C++",
        "Go", "Rust", "HTML", "CSS", "Tailwind", "Machine Learning", "PyTorch", "TensorFlow",
    ]
    detected_skills = normalize_skills([skill for skill in common_skills if skill_in_text(skill, lower_text)])

    # Experience level classification
    if any(k in lower_text for k in ["senior", "lead", "architect", "staff", "principal"]):
        level = "Senior"
    elif any(k in lower_text for k in ["mid-level", "mid level", "3+ years", "4+ years", "5+ years"]):
        level = "Mid-Level"
    elif any(k in lower_text for k in ["junior", "associate", "1+ year", "2+ years"]):
        level = "Junior"
    elif any(k in lower_text for k in ["student", "pursuing", "intern", "undergraduate"]):
        level = "Student"
    else:
        level = "Fresher"

    # Education detection
    education: list[EducationItem] = []
    edu_match = re.search(r"(b\.?tech|b\.?s\.?|bachelor|m\.?s\.?|master|phd|diploma)\b[^\n]*", lower_text)
    if edu_match:
        education.append(
            EducationItem(
                degree=edu_match.group(0).title(),
                institution="University / College mentioned in resume",
                year="Present" if "present" in lower_text else None,
            )
        )

    # A fallback parser cannot safely infer structured projects or employment
    # records from section headings alone. Leave these empty rather than inventing
    # a company, title, or project that the candidate did not state explicitly.
    projects: list[ProjectItem] = []
    work_experience: list[WorkExperienceItem] = []

    # Suggested roles
    suggested_roles = ["Software Engineer"]
    if "backend" in lower_text or "fastapi" in lower_text or "python" in lower_text:
        suggested_roles.extend(["Backend Developer", "Python Developer"])
    if "react" in lower_text or "frontend" in lower_text:
        suggested_roles.append("Full Stack Developer")
    if "data" in lower_text or "machine learning" in lower_text:
        suggested_roles.append("Data Scientist / ML Engineer")

    return AIResumeAnalysisResult(
        summary=lines[0] if lines else "No readable resume content was available.",
        skills=detected_skills,
        education=education,
        projects=projects,
        certifications=[],
        work_experience=work_experience,
        strengths=[
            f"{len(detected_skills)} verified technical skills extracted" if detected_skills else "Add a clear skills section to improve profile accuracy",
        ],
        weaknesses=[
            "Quantify key achievements with measurable numerical metrics",
            "Include project, experience, and education details where available",
        ],
        experience_level=level,
        suggested_roles=list(dict.fromkeys(suggested_roles)),
    )


def analyze_resume_text(text: str) -> AIResumeAnalysisResult:
    """Analyze resume text using OpenAI structured JSON output with fast fallback."""
    if not is_openai_configured():
        return _heuristic_resume_analysis(text)

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY.strip(), timeout=10.0, max_retries=0)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Here is the resume text to analyze:\n\n{text}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        content = response.choices[0].message.content or "{}"
        parsed_json = json.loads(content)
        result = AIResumeAnalysisResult.model_validate(parsed_json)
        return result

    except Exception as exc:
        logger.warning(
            f"OpenAI API call failed ({exc}). Falling back to heuristic resume analysis.",
        )
        return _heuristic_resume_analysis(text)
