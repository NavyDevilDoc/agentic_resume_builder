"""Tests for gap analysis — unit (mocked) + integration (live)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import GapReport, IntelligenceBrief, ResumeSchema, ResumeSection
from modules.resume.analyzer import AnalysisError, analyze_gaps


SAMPLE_RESUME = ResumeSchema(
    contact={"name": "Jeremy Springston", "email": "jeremy@example.com"},
    summary="AI/ML Engineer with 20+ years of leadership experience.",
    experience=[
        ResumeSection(
            section_type="experience",
            raw_text="Booz Allen Hamilton, AI/ML Engineer 3",
            bullets=[
                "Coordinating critical engineering decisions for PEO IWS 11.0",
                "Architected semantic search and LLM-based productivity tools",
            ],
        )
    ],
    skills=["Python", "PyTorch", "TensorFlow", "LangChain", "RAG"],
    education=[
        ResumeSection(
            section_type="education",
            raw_text="MS Johns Hopkins University, Applied Mathematics 2021",
        )
    ],
    certifications=[],
)

SAMPLE_JD = (
    "Sr. Principal AI Systems Engineer at Northrop Grumman. "
    "Required: Python, Java, AWS, Azure, AI/ML frameworks, SQL, "
    "distributed computing, cybersecurity for AI systems."
)

SAMPLE_INTEL = IntelligenceBrief(
    role_category="AI/ML Engineer",
    industry="Defense",
    week="2026-W11",
    what_recruiters_reward=["quantified impact", "clearance mentioned early"],
    what_recruiters_skip=["generic summaries"],
    red_flags=["typos"],
    legs_populated=["linkedin"],
)

VALID_GAP_RESPONSE = json.dumps({
    "gaps": [
        {
            "severity": "high",
            "category": "missing_keywords",
            "description": "Resume lacks AWS and Azure cloud experience",
            "suggested_action": "Add cloud platform experience to skills and bullet points",
        },
        {
            "severity": "medium",
            "category": "absent_quantification",
            "description": "First bullet lacks measurable outcome",
            "suggested_action": "Add metrics showing scope or impact",
        },
    ],
    "jd_provided": True,
})

VALID_GAP_NO_JD_RESPONSE = json.dumps({
    "gaps": [
        {
            "severity": "low",
            "category": "format_issues",
            "description": "Summary could be more targeted",
            "suggested_action": "Tailor summary to specific role type",
        },
    ],
    "jd_provided": False,
})


def _mock_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


# ── Unit tests (mocked Claude) ─────────────────────────────────────────

class TestAnalyzeGapsMocked:
    @patch("modules.resume.analyzer.anthropic.Anthropic")
    def test_with_jd_and_intel(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(VALID_GAP_RESPONSE)

        result = analyze_gaps(SAMPLE_RESUME, SAMPLE_JD, SAMPLE_INTEL)

        assert isinstance(result, GapReport)
        assert result.jd_provided is True
        assert len(result.gaps) == 2
        assert result.gaps[0].severity == "high"
        assert result.gaps[0].category == "missing_keywords"

    @patch("modules.resume.analyzer.anthropic.Anthropic")
    def test_without_jd(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(VALID_GAP_NO_JD_RESPONSE)

        result = analyze_gaps(SAMPLE_RESUME, job_posting=None, intelligence_brief=SAMPLE_INTEL)

        assert isinstance(result, GapReport)
        assert result.jd_provided is False
        assert len(result.gaps) == 1

    @patch("modules.resume.analyzer.anthropic.Anthropic")
    def test_without_jd_or_intel(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(VALID_GAP_NO_JD_RESPONSE)

        result = analyze_gaps(SAMPLE_RESUME, job_posting=None, intelligence_brief=None)

        assert isinstance(result, GapReport)

    @patch("modules.resume.analyzer.anthropic.Anthropic")
    def test_uses_jd_prompt_when_jd_provided(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(VALID_GAP_RESPONSE)

        analyze_gaps(SAMPLE_RESUME, SAMPLE_JD, SAMPLE_INTEL)

        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "<job_description>" in user_msg

    @patch("modules.resume.analyzer.anthropic.Anthropic")
    def test_uses_no_jd_prompt_when_no_jd(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(VALID_GAP_NO_JD_RESPONSE)

        analyze_gaps(SAMPLE_RESUME, job_posting=None, intelligence_brief=SAMPLE_INTEL)

        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "<job_description>" not in user_msg

    @patch("modules.resume.analyzer.anthropic.Anthropic")
    def test_strips_markdown_fences(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        fenced = f"```json\n{VALID_GAP_RESPONSE}\n```"
        mock_client.messages.create.return_value = _mock_response(fenced)

        result = analyze_gaps(SAMPLE_RESUME, SAMPLE_JD)
        assert isinstance(result, GapReport)

    @patch("modules.resume.analyzer.anthropic.Anthropic")
    def test_empty_gaps_list(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        empty_response = json.dumps({"gaps": [], "jd_provided": True})
        mock_client.messages.create.return_value = _mock_response(empty_response)

        result = analyze_gaps(SAMPLE_RESUME, SAMPLE_JD)
        assert result.gaps == []

    @patch("modules.resume.analyzer.anthropic.Anthropic")
    def test_invalid_json_raises(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response("not json")

        with pytest.raises(AnalysisError, match="invalid"):
            analyze_gaps(SAMPLE_RESUME, SAMPLE_JD)

    @patch("modules.resume.analyzer.anthropic.Anthropic")
    def test_api_error_raises(self, mock_anthropic_cls):
        import anthropic

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="rate limited", request=MagicMock(), body=None
        )

        with pytest.raises(AnalysisError, match="Failed"):
            analyze_gaps(SAMPLE_RESUME, SAMPLE_JD)


# ── Integration tests (live Claude) ────────────────────────────────────

@pytest.mark.integration
class TestAnalyzeGapsLive:
    """Live API tests — only run with: pytest -m integration"""

    def _get_resume_schema(self) -> ResumeSchema:
        """Parse and structure the real test fixture."""
        from pathlib import Path
        from modules.resume.parser import parse_docx
        from modules.resume.structurer import structure_resume

        docx_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "sample_resumes"
            / "sample_resume.docx"
        )
        if not docx_path.exists():
            pytest.skip("DOCX fixture not available")
        text = parse_docx(docx_path.read_bytes())
        return structure_resume(text)

    def _get_jd(self) -> str:
        from pathlib import Path
        jd_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "sample_job_postings"
            / "northrop_grumman_sr_principal_ai.txt"
        )
        if not jd_path.exists():
            pytest.skip("JD fixture not available")
        return jd_path.read_text(encoding="utf-8")

    def test_live_gap_analysis_with_jd(self):
        resume = self._get_resume_schema()
        jd = self._get_jd()

        result = analyze_gaps(resume, job_posting=jd)

        assert isinstance(result, GapReport)
        assert result.jd_provided is True
        # Should find at least one gap
        assert len(result.gaps) > 0
        # Verify gap structure
        for gap in result.gaps:
            assert gap.severity in ("high", "medium", "low")
            assert len(gap.description) > 0
            assert len(gap.suggested_action) > 0

    def test_live_gap_analysis_without_jd(self):
        resume = self._get_resume_schema()

        result = analyze_gaps(resume, job_posting=None)

        assert isinstance(result, GapReport)
        assert result.jd_provided is False
