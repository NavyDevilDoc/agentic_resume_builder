"""Tests for rewrite verification — unit (mocked) + integration (live)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import (
    ResumeSchema,
    ResumeSection,
    RevisedResumeSchema,
    VerificationFlag,
    VerificationReport,
)
from modules.resume.verifier import VerificationError, verify_rewrite


# ── Shared fixtures ────────────────────────────────────────────────────

ORIGINAL = ResumeSchema(
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

# Revised with some legitimate edits and some fabricated content
REVISED_WITH_FLAGS = RevisedResumeSchema(
    contact={"name": "Jeremy Springston", "email": "jeremy@example.com"},
    summary="AI/ML Engineer with 20+ years of leadership experience.",
    experience=[
        ResumeSection(
            section_type="experience",
            raw_text="Booz Allen Hamilton, AI/ML Engineer 3",
            bullets=[
                "Coordinating critical engineering decisions across 12 weapon systems for PEO IWS 11.0",
                "Architected semantic search and LLM-based productivity tools adopted by 50+ personnel",
            ],
        )
    ],
    skills=["Python", "PyTorch", "TensorFlow", "LangChain", "RAG", "AWS"],
    education=[
        ResumeSection(
            section_type="education",
            raw_text="MS Johns Hopkins University, Applied Mathematics 2021",
        )
    ],
    certifications=[],
    rewrite_level_used="edit",
    change_log=["Added metrics", "Added AWS"],
)

REVISED_CLEAN = RevisedResumeSchema(
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
    rewrite_level_used="edit",
    change_log=["Minor verb improvements"],
)


# ── Mock responses ─────────────────────────────────────────────────────

FLAGGED_RESPONSE = json.dumps({
    "flags": [
        {
            "category": "new_metric",
            "severity": "warning",
            "original_text": "Coordinating critical engineering decisions for PEO IWS 11.0",
            "revised_text": "Coordinating critical engineering decisions across 12 weapon systems for PEO IWS 11.0",
            "explanation": "The number '12 weapon systems' does not appear in the original resume",
        },
        {
            "category": "new_metric",
            "severity": "warning",
            "original_text": "Architected semantic search and LLM-based productivity tools",
            "revised_text": "Architected semantic search and LLM-based productivity tools adopted by 50+ personnel",
            "explanation": "The metric '50+ personnel' was not in the original",
        },
        {
            "category": "new_skill",
            "severity": "info",
            "original_text": None,
            "revised_text": "AWS added to skills section",
            "explanation": "AWS was not in the original skills list but may be a valid skill to add",
        },
    ],
    "verified_clean": False,
})

CLEAN_RESPONSE = json.dumps({
    "flags": [],
    "verified_clean": True,
})


def _mock_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    response.stop_reason = "end_turn"
    return response


# ── Unit tests (mocked Claude) ─────────────────────────────────────────

class TestVerifyRewriteMocked:
    @patch("modules.resume.verifier.anthropic.Anthropic")
    def test_flags_fabricated_content(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(FLAGGED_RESPONSE)

        report = verify_rewrite(ORIGINAL, REVISED_WITH_FLAGS)

        assert isinstance(report, VerificationReport)
        assert not report.verified_clean
        assert len(report.flags) == 3

        warnings = [f for f in report.flags if f.severity == "warning"]
        infos = [f for f in report.flags if f.severity == "info"]
        assert len(warnings) == 2
        assert len(infos) == 1

        # Check flag categories
        categories = {f.category for f in report.flags}
        assert "new_metric" in categories
        assert "new_skill" in categories

    @patch("modules.resume.verifier.anthropic.Anthropic")
    def test_clean_verification(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(CLEAN_RESPONSE)

        report = verify_rewrite(ORIGINAL, REVISED_CLEAN)

        assert isinstance(report, VerificationReport)
        assert report.verified_clean
        assert len(report.flags) == 0

    @patch("modules.resume.verifier.anthropic.Anthropic")
    def test_sends_both_resumes_in_prompt(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(CLEAN_RESPONSE)

        verify_rewrite(ORIGINAL, REVISED_CLEAN)

        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "<original_resume>" in user_msg
        assert "<revised_resume>" in user_msg
        assert "Jeremy Springston" in user_msg

    @patch("modules.resume.verifier.anthropic.Anthropic")
    def test_api_error_raises(self, mock_anthropic_cls):
        import anthropic

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="rate limited", request=MagicMock(), body=None
        )

        with pytest.raises(VerificationError, match="Failed to verify"):
            verify_rewrite(ORIGINAL, REVISED_WITH_FLAGS)

    @patch("modules.resume.verifier.anthropic.Anthropic")
    def test_invalid_json_raises(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response("not json")

        with pytest.raises(VerificationError, match="invalid"):
            verify_rewrite(ORIGINAL, REVISED_WITH_FLAGS)

    @patch("modules.resume.verifier.anthropic.Anthropic")
    def test_handles_markdown_fences(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        fenced = f"```json\n{CLEAN_RESPONSE}\n```"
        mock_client.messages.create.return_value = _mock_response(fenced)

        report = verify_rewrite(ORIGINAL, REVISED_CLEAN)
        assert report.verified_clean


# ── Schema tests ───────────────────────────────────────────────────────

class TestVerificationSchemas:
    def test_valid_flag(self):
        flag = VerificationFlag(
            category="new_metric",
            severity="warning",
            original_text="some original text",
            revised_text="some revised text with 42% improvement",
            explanation="42% was not in the original",
        )
        assert flag.category == "new_metric"

    def test_flag_null_original(self):
        flag = VerificationFlag(
            category="new_skill",
            severity="info",
            original_text=None,
            revised_text="AWS added",
            explanation="Not in original skills",
        )
        assert flag.original_text is None

    def test_invalid_category_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            VerificationFlag(
                category="invalid_category",
                severity="warning",
                revised_text="text",
                explanation="reason",
            )

    def test_report_clean(self):
        report = VerificationReport(flags=[], verified_clean=True)
        assert report.verified_clean

    def test_report_with_flags(self):
        report = VerificationReport(
            flags=[
                VerificationFlag(
                    category="new_metric",
                    severity="warning",
                    revised_text="50+ users",
                    explanation="Not in original",
                )
            ],
            verified_clean=False,
        )
        assert not report.verified_clean
        assert len(report.flags) == 1


# ── Integration tests (live Claude) ────────────────────────────────────

@pytest.mark.integration
class TestVerifyRewriteLive:
    """Live API tests — only run with: pytest -m integration"""

    def _get_fixtures(self):
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
        return resume, revised

    def test_live_verification(self):
        original, revised = self._get_fixtures()

        report = verify_rewrite(original, revised)

        assert isinstance(report, VerificationReport)
        assert isinstance(report.verified_clean, bool)

        # An edit-level rewrite should produce some flags (metrics, keywords)
        # but this is not guaranteed, so we just validate structure
        for flag in report.flags:
            assert flag.category in (
                "new_company", "new_title", "new_date", "new_metric",
                "new_skill", "new_certification", "new_claim",
            )
            assert flag.severity in ("warning", "info")
            assert len(flag.explanation) > 0
            assert len(flag.revised_text) > 0
