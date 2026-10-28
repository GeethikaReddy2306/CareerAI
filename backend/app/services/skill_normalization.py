"""Canonical skill names and safe matching helpers shared by career services.

Matching operates on whole normalised phrases, never substrings.  This keeps
``Java`` from matching ``JavaScript`` and makes aliases such as ReactJS and
React.js behave identically throughout the product.
"""
from __future__ import annotations

import re
from collections.abc import Iterable


SKILL_ALIASES: dict[str, str] = {
    "react": "React", "reactjs": "React", "react.js": "React", "react js": "React",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js", "node js": "Node.js",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "psql": "PostgreSQL",
    "javascript": "JavaScript", "js": "JavaScript", "typescript": "TypeScript", "ts": "TypeScript",
    "golang": "Go", "go lang": "Go", "go": "Go", "python": "Python", "java": "Java",
    "rest": "REST APIs", "rest api": "REST APIs", "rest apis": "REST APIs",
    "restful": "REST APIs", "restful api": "REST APIs", "restful apis": "REST APIs",
    "k8s": "Kubernetes", "kubernetes": "Kubernetes", "mongo": "MongoDB", "mongodb": "MongoDB",
    "aws": "AWS", "amazon web services": "AWS", "gcp": "GCP", "google cloud": "GCP",
    "google cloud platform": "GCP", "azure": "Azure", "microsoft azure": "Azure",
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask", "graphql": "GraphQL",
    "spring": "Spring Boot", "springboot": "Spring Boot", "spring boot": "Spring Boot",
    "docker": "Docker", "containerization": "Docker", "containers": "Docker",
    "ci/cd": "CI/CD", "cicd": "CI/CD", "ci cd": "CI/CD", "git": "Git", "github": "Git",
    "linux": "Linux", "unix": "Linux", "sql": "SQL", "mysql": "MySQL", "sqlite": "SQLite",
    "html": "HTML/CSS", "css": "HTML/CSS", "html/css": "HTML/CSS", "tailwind": "HTML/CSS",
    "system design": "System Design", "system architecture": "System Design",
    "message queue": "Message Queues", "message queues": "Message Queues",
    "rabbitmq": "Message Queues", "kafka": "Kafka", "redis": "Caching", "memcached": "Caching",
    "caching": "Caching", "pytest": "Unit Testing", "unit test": "Unit Testing",
    "unit testing": "Unit Testing", "microservices": "Microservices",
    "machine learning": "Machine Learning", "pytorch": "PyTorch", "tensorflow": "TensorFlow",
}


def normalize_skill(skill: str) -> str:
    """Return the canonical skill label without guessing an unknown skill."""
    cleaned = re.sub(r"[\s_]+", " ", (skill or "").strip().lower())
    return SKILL_ALIASES.get(cleaned, " ".join(word.capitalize() for word in cleaned.split()))


def normalize_skills(skills: Iterable[str]) -> list[str]:
    """Normalise and de-duplicate a sequence while preserving its order."""
    seen: set[str] = set()
    result: list[str] = []
    for skill in skills:
        canonical = normalize_skill(skill)
        if canonical and canonical.casefold() not in seen:
            seen.add(canonical.casefold())
            result.append(canonical)
    return result


def skill_in_text(skill: str, text: str) -> bool:
    """Match one recognised alias as a full phrase in text."""
    canonical = normalize_skill(skill)
    variants = [alias for alias, value in SKILL_ALIASES.items() if value.casefold() == canonical.casefold()]
    variants.append(canonical.lower())
    return any(re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text or "", re.I) for alias in variants)
