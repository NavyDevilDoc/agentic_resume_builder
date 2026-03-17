"""Tests for the rewrite engine (all three escalation levels) — unit + integration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import (
    GapItem,
    GapReport,
    IntelligenceBrief,
    ResumeSchema,
    ResumeSection,
    RevisedResumeSchema,
    StyleProfile,
)
from modules.resume.rewriter import RewriteError, rewrite_resume


# ── Shared fixtures ────────────────────────────────────────────────────

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

SAMPLE_STYLE = StyleProfile(
    formality_level="formal",
    sentence_length="mixed",
    structure_tendency="action_first",
    quantification_habit="frequent",
    vocabulary_register="Technical, acronym-heavy, defense sector jargon",
)

SAMPLE_GAPS = GapReport(
    gaps=[
        GapItem(
            severity="high",
            category="missing_keywords",
            description="No AWS/Azure mentioned",
            suggested_action="Add cloud platform experience",
        ),
        GapItem(
            severity="medium",
            category="absent_quantification",
            description="First bullet lacks metrics",
            suggested_action="Add measurable outcomes",
        ),
    ],
    jd_provided=True,
)

SAMPLE_INTEL = IntelligenceBrief(
    role_category="AI/ML Engineer",
    industry="Defense",
    week="2026-W11",
    what_recruiters_reward=["quantified impact"],
    what_recruiters_skip=["generic summaries"],
    red_flags=["typos"],
    format_preferences=["one page"],
    legs_populated=["linkedin"],
)

# ── Mock response data ─────────────────────────────────────────────────

LEVEL1_RESPONSE = json.dumps({
    "rewrite_level_used": "suggestions",
    "sections": [
        {
            "section_name": "experience",
            "suggestions": [
                {
                    "target": "Coordinating critical engineering decisions for PEO IWS 11.0",
                    "suggestion": "Add quantified scope — how many systems or personnel affected",
                    "priority": "high",
                },
                {
                    "target": "Architected semantic search and LLM-based productivity tools",
                    "suggestion": "Add adoption metrics — how many users, time saved",
                    "priority": "medium",
                },
            ],
        }
    ],
    "change_log": [
        "Suggest adding quantified scope to PEO IWS bullet",
        "Suggest adding adoption metrics to semantic search bullet",
    ],
})

LEVEL2_RESPONSE = json.dumps({
    "contact": {"name": "Jeremy Springston", "email": "jeremy@example.com"},
    "summary": "AI/ML Engineer with 20+ years of leadership experience.",
    "experience": [
        {
            "section_type": "experience",
            "raw_text": "Booz Allen Hamilton, AI/ML Engineer 3",
            "bullets": [
                "Coordinating critical engineering decisions across 12 weapon systems for PEO IWS 11.0",
                "Architected semantic search and LLM-based productivity tools adopted by 50+ IWS personnel",
            ],
        }
    ],
    "skills": ["Python", "PyTorch", "TensorFlow", "LangChain", "RAG", "AWS"],
    "education": [
        {
            "section_type": "education",
            "raw_text": "MS Johns Hopkins University, Applied Mathematics 2021",
        }
    ],
    "certifications": [],
    "rewrite_level_used": "edit",
    "change_log": [
        "Added quantified scope (12 weapon systems) to PEO IWS bullet",
        "Added adoption metric (50+ personnel) to semantic search bullet",
        "Added AWS to skills to address missing cloud keyword",
    ],
})

LEVEL3_RESPONSE = json.dumps({
    "contact": {"name": "Jeremy Springston", "email": "jeremy@example.com"},
    "summary": "AI/ML Engineer and systems architect with 20+ years leading technical teams in defense environments. Specialized in deploying production AI pipelines on cloud and edge infrastructure.",
    "experience": [
        {
            "section_type": "experience",
            "raw_text": "Booz Allen Hamilton, AI/ML Engineer 3",
            "bullets": [
                "Lead AI systems engineer for PEO IWS 11.0 counter-unmanned program, coordinating engineering decisions across 12 weapon systems and 4 development teams",
                "Designed and deployed semantic search platform and LLM productivity suite (email assistant, prompt tools) on AWS infrastructure, adopted by 50+ IWS personnel, reducing document retrieval time by 60%",
            ],
        }
    ],
    "skills": ["Python", "PyTorch", "TensorFlow", "LangChain", "RAG", "AWS", "Docker", "MLOps"],
    "education": [
        {
            "section_type": "education",
            "raw_text": "MS Johns Hopkins University, Applied Mathematics 2021",
        }
    ],
    "certifications": [],
    "rewrite_level_used": "full_rewrite",
    "change_log": [
        "Rewrote summary to emphasize systems architecture and cloud/edge deployment (gap: misaligned_narrative)",
        "Rewrote PEO IWS bullet with quantified scope — 12 systems, 4 teams (gap: absent_quantification)",
        "Rewrote semantic search bullet with AWS infrastructure context and 60% time reduction metric (gaps: missing_keywords, absent_quantification)",
        "Added MLOps to skills (gap: missing_keywords, per intelligence: recruiters reward MLOps terminology)",
    ],
})


def _mock_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    response.stop_reason = "end_turn"
    return response


# ── Unit tests: Level 1 (Suggestions) ─────────────────────────────────

class TestLevel1Mocked:
    @patch("modules.resume.rewriter.anthropic.Anthropic")
    def test_suggestions_returned(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(LEVEL1_RESPONSE)

        result = rewrite_resume(
            SAMPLE_RESUME, SAMPLE_STYLE, SAMPLE_GAPS, level="suggestions"
        )

        assert isinstance(result, dict)
        assert result["rewrite_level_used"] == "suggestions"
        assert len(result["sections"]) > 0
        assert len(result["change_log"]) > 0

    @patch("modules.resume.rewriter.anthropic.Anthropic")
    def test_suggestions_with_intel_and_voice(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(LEVEL1_RESPONSE)

        result = rewrite_resume(
            SAMPLE_RESUME,
            SAMPLE_STYLE,
            SAMPLE_GAPS,
            level="suggestions",
            intelligence_brief=SAMPLE_INTEL,
            voice_sample="I write directly and technically.",
        )

        assert isinstance(result, dict)
        # Verify intel and voice were included in prompt
        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "intelligence_brief" in user_msg
        assert "voice_sample" in user_msg


# ── Unit tests: Level 2 (Edit) ────────────────────────────────────────

class TestLevel2Mocked:
    @patch("modules.resume.rewriter.anthropic.Anthropic")
    def test_edit_returns_revised_schema(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(LEVEL2_RESPONSE)

        result = rewrite_resume(
            SAMPLE_RESUME, SAMPLE_STYLE, SAMPLE_GAPS, level="edit"
        )

        assert isinstance(result, RevisedResumeSchema)
        assert result.rewrite_level_used == "edit"
        assert len(result.change_log) > 0
        assert "AWS" in result.skills

    @patch("modules.resume.rewriter.anthropic.Anthropic")
    def test_edit_preserves_contact(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(LEVEL2_RESPONSE)

        result = rewrite_resume(
            SAMPLE_RESUME, SAMPLE_STYLE, SAMPLE_GAPS, level="edit"
        )

        assert result.contact["name"] == "Jeremy Springston"


# ── Unit tests: Level 3 (Full Rewrite) ────────────────────────────────

class TestLevel3Mocked:
    @patch("modules.resume.rewriter.anthropic.Anthropic")
    def test_full_rewrite_returns_revised_schema(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(LEVEL3_RESPONSE)

        result = rewrite_resume(
            SAMPLE_RESUME, SAMPLE_STYLE, SAMPLE_GAPS, level="full_rewrite"
        )

        assert isinstance(result, RevisedResumeSchema)
        assert result.rewrite_level_used == "full_rewrite"
        assert len(result.change_log) > 0
        assert "MLOps" in result.skills

    @patch("modules.resume.rewriter.anthropic.Anthropic")
    def test_full_rewrite_change_log_cites_gaps(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(LEVEL3_RESPONSE)

        result = rewrite_resume(
            SAMPLE_RESUME, SAMPLE_STYLE, SAMPLE_GAPS, level="full_rewrite"
        )

        # Change log should reference gap categories or intelligence
        all_changes = " ".join(result.change_log).lower()
        assert "gap" in all_changes or "intelligence" in all_changes


# ── Unit tests: Error handling ─────────────────────────────────────────

class TestRewriterErrors:
    def test_invalid_level_raises(self):
        with pytest.raises(RewriteError, match="Invalid rewrite level"):
            rewrite_resume(
                SAMPLE_RESUME, SAMPLE_STYLE, SAMPLE_GAPS, level="invalid"
            )

    @patch("modules.resume.rewriter.anthropic.Anthropic")
    def test_api_error_raises(self, mock_anthropic_cls):
        import anthropic

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="rate limited", request=MagicMock(), body=None
        )

        with pytest.raises(RewriteError, match="Failed to generate"):
            rewrite_resume(
                SAMPLE_RESUME, SAMPLE_STYLE, SAMPLE_GAPS, level="edit"
            )

    @patch("modules.resume.rewriter.anthropic.Anthropic")
    def test_invalid_json_raises(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response("not json at all")

        with pytest.raises(RewriteError, match="invalid rewrite response"):
            rewrite_resume(
                SAMPLE_RESUME, SAMPLE_STYLE, SAMPLE_GAPS, level="edit"
            )

    @patch("modules.resume.rewriter.anthropic.Anthropic")
    def test_bad_schema_raises(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        bad_data = json.dumps({"contact": "not a dict", "skills": "not a list"})
        mock_client.messages.create.return_value = _mock_response(bad_data)

        with pytest.raises(RewriteError, match="did not match"):
            rewrite_resume(
                SAMPLE_RESUME, SAMPLE_STYLE, SAMPLE_GAPS, level="edit"
            )


# ── Integration tests (live Claude) ────────────────────────────────────

@pytest.mark.integration
class TestRewriterLive:
    """Live API tests — only run with: pytest -m integration"""

    def _get_fixtures(self):
        from modules.resume.parser import parse_docx
        from modules.resume.structurer import structure_resume
        from modules.resume.style import extract_style
        from modules.resume.analyzer import analyze_gaps

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

        return resume, style, gaps

    def test_live_level1_suggestions(self):
        resume, style, gaps = self._get_fixtures()

        result = rewrite_resume(resume, style, gaps, level="suggestions")

        assert isinstance(result, dict)
        assert result["rewrite_level_used"] == "suggestions"
        assert "sections" in result or "change_log" in result

    def test_live_level2_edit(self):
        resume, style, gaps = self._get_fixtures()

        result = rewrite_resume(resume, style, gaps, level="edit")

        assert isinstance(result, RevisedResumeSchema)
        assert result.rewrite_level_used == "edit"
        assert len(result.change_log) > 0
        assert len(result.experience) > 0

    def test_live_level3_full_rewrite(self):
        resume, style, gaps = self._get_fixtures()

        result = rewrite_resume(resume, style, gaps, level="full_rewrite")

        assert isinstance(result, RevisedResumeSchema)
        assert result.rewrite_level_used == "full_rewrite"
        assert len(result.change_log) > 0
        assert len(result.experience) > 0
