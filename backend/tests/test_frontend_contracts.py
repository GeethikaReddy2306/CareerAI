from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"


def test_ats_ui_has_no_ai_review_and_keeps_deterministic_sections():
    source = (FRONTEND / "AtsScore.jsx").read_text(encoding="utf-8")
    assert "AIReview" not in source
    assert "Detailed checks" in source
    assert "Improvements" in source


def test_job_match_partial_card_has_meaningful_empty_state():
    source = (FRONTEND / "JobMatch.jsx").read_text(encoding="utf-8")
    assert "No partially matched skills found." in source


def test_interview_pages_preserve_source_attribution_and_validate_evaluations():
    prep = (FRONTEND / "InterviewPrep.jsx").read_text(encoding="utf-8")
    mock = (FRONTEND / "MockInterview.jsx").read_text(encoding="utf-8")

    assert "target_role: role" in prep
    assert "Profile-based fallback" in prep
    assert "Demo mode — not AI-generated" in prep
    assert "isValidEvaluation" in mock
    assert "Profile-based evaluation" in mock
    assert "Demo evaluation — rule-based" in mock
    assert "getInterviewSession" in mock
    assert "Optional job description" in mock
