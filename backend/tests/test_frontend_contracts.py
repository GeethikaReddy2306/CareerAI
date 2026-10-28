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
