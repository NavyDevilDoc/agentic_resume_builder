"""Tests for JD keyword scoring — unit (mocked) + integration (live)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import KeywordReport, ResumeSection, RevisedResumeSchema
from modules.scoring.keyword_match import ScoringError, score_keywords, _build_resume_text


# ── Shared fixtures ────────────────────────────────────────────────────

SAMPLE_REVISED = RevisedResumeSchema(
    contact={"name": "Jeremy Springston"},
    summary="AI/ML Engineer with cloud and edge deployment experience.",
    experience=[
        ResumeSection(
            section_type="experience",
            raw_text="Booz Allen Hamilton, AI/ML Engineer 3",
            bullets=[
                "Deployed semantic search on AWS infrastructure",
                "Built RAG pipeline with Python and LangChain",
            ],
        )
    ],
    skills=["Python", "PyTorch", "TensorFlow", "AWS", "Docker", "SQL", "RAG"],
    education=[
        ResumeSection(
            section_type="education",
            raw_text="MS Johns Hopkins University, Applied Mathematics",
        )
    ],
    certifications=[],
    rewrite_level_used="edit",
    change_log=["Added AWS"],
)

SAMPLE_JD = (
    "Required: Python, Java, AWS, Azure, SQL, Docker, "
    "distributed computing, cybersecurity for AI systems."
)

EXTRACTED_KEYWORDS_RESPONSE = json.dumps({
    "keywords": [
        "python", "java", "aws", "azure", "sql",
        "docker", "distributed computing", "cybersecurity",
    ]
})


def _mock_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


# ── Unit tests: resume text builder ───────────────────────────────────

class TestBuildResumeText:
    def test_flattens_all_fields(self):
        text = _build_resume_text(SAMPLE_REVISED)
        assert "python" in text
        assert "aws" in text
        assert "semantic search" in text
        assert "johns hopkins" in text

    def test_handles_empty_resume(self):
        empty = RevisedResumeSchema(
            contact={},
            rewrite_level_used="edit",
            change_log=[],
        )
        text = _build_resume_text(empty)
        assert text.strip() == ""


# ── Unit tests: keyword scoring (mocked) ──────────────────────────────

class TestScoreKeywordsMocked:
    @patch("modules.scoring.keyword_match.anthropic.Anthropic")
    def test_scoring_with_matches(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(
            EXTRACTED_KEYWORDS_RESPONSE
        )

        report = score_keywords(SAMPLE_REVISED, SAMPLE_JD)

        assert isinstance(report, KeywordReport)
        assert report.match_pct > 0
        assert "python" in report.present_terms
        assert "aws" in report.present_terms
        assert "docker" in report.present_terms
        assert "sql" in report.present_terms
        assert "java" in report.missing_terms
        assert "azure" in report.missing_terms

    @patch("modules.scoring.keyword_match.anthropic.Anthropic")
    def test_all_keywords_present(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        # Only keywords that are in the resume
        small_response = json.dumps({"keywords": ["python", "aws", "docker"]})
        mock_client.messages.create.return_value = _mock_response(small_response)

        report = score_keywords(SAMPLE_REVISED, SAMPLE_JD)

        assert report.match_pct == 100.0
        assert len(report.missing_terms) == 0

    @patch("modules.scoring.keyword_match.anthropic.Anthropic")
    def test_no_keywords_present(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        missing_response = json.dumps({"keywords": ["rust", "golang", "kubernetes"]})
        mock_client.messages.create.return_value = _mock_response(missing_response)

        report = score_keywords(SAMPLE_REVISED, SAMPLE_JD)

        assert report.match_pct == 0.0
        assert len(report.present_terms) == 0
        assert len(report.missing_terms) == 3

    @patch("modules.scoring.keyword_match.anthropic.Anthropic")
    def test_empty_keywords_extracted(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(
            json.dumps({"keywords": []})
        )

        report = score_keywords(SAMPLE_REVISED, SAMPLE_JD)

        assert report.match_pct == 0.0
        assert report.present_terms == []
        assert report.missing_terms == []

    @patch("modules.scoring.keyword_match.anthropic.Anthropic")
    def test_api_error_raises(self, mock_anthropic_cls):
        import anthropic

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="rate limited", request=MagicMock(), body=None
        )

        with pytest.raises(ScoringError, match="Failed to extract"):
            score_keywords(SAMPLE_REVISED, SAMPLE_JD)

    @patch("modules.scoring.keyword_match.anthropic.Anthropic")
    def test_invalid_json_raises(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response("not json")

        with pytest.raises(ScoringError, match="invalid"):
            score_keywords(SAMPLE_REVISED, SAMPLE_JD)


# ── Integration tests (live Claude) ────────────────────────────────────

@pytest.mark.integration
class TestScoreKeywordsLive:
    """Live API tests — only run with: pytest -m integration"""

    def _get_revised_resume(self) -> RevisedResumeSchema:
        from modules.resume.parser import parse_docx
        from modules.resume.structurer import structure_resume
        from modules.resume.style import extract_style
        from modules.resume.analyzer import analyze_gaps
        from modules.resume.rewriter import rewrite_resume

        fixtures_dir = Path(__file__).parent.parent / "fixtures"
        docx_path = fixtures_dir / "sample_resumes" / "sample_resume.docx"
        jd_path = fixtures_dir / "sample_job_postings" / "northrop_grumman_sr_principal_ai.txt"

        if not docx_path.exists():
            pytest.skip("DOCX fixture not available")

        text = parse_docx(docx_path.read_bytes())
        resume = structure_resume(text)
        style = extract_style(text)
        jd = jd_path.read_text(encoding="utf-8") if jd_path.exists() else None
        gaps = analyze_gaps(resume, job_posting=jd)
        revised = rewrite_resume(resume, style, gaps, level="edit")

        assert isinstance(revised, RevisedResumeSchema)
        return revised

    def test_live_keyword_scoring(self):
        revised = self._get_revised_resume()

        jd_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "sample_job_postings"
            / "northrop_grumman_sr_principal_ai.txt"
        )
        jd = jd_path.read_text(encoding="utf-8")

        report = score_keywords(revised, jd)

        assert isinstance(report, KeywordReport)
        assert report.match_pct >= 0
        assert len(report.present_terms) + len(report.missing_terms) > 0
