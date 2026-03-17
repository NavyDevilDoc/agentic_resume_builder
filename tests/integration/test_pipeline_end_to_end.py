"""End-to-end pipeline integration tests.

Mocked path: exercises the full pipeline with mocked API calls (runs in default suite).
Live path: exercises the full pipeline with real APIs (gated behind @pytest.mark.integration).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import (
    GapReport,
    IntelligenceBrief,
    KeywordReport,
    ResumeSchema,
    RevisedResumeSchema,
    StyleProfile,
)
from modules.intelligence.cache import clear_cache
from modules.resume.parser import parse_docx, parse_resume
from modules.resume.structurer import structure_resume
from modules.resume.style import extract_style
from modules.resume.analyzer import analyze_gaps
from modules.resume.rewriter import rewrite_resume
from modules.scoring.keyword_match import score_keywords
from modules.output.renderer import render_docx
from modules.intelligence.distiller import distill_intelligence


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
DOCX_PATH = FIXTURES_DIR / "sample_resumes" / "sample_resume.docx"
JD_PATH = FIXTURES_DIR / "sample_job_postings" / "northrop_grumman_sr_principal_ai.txt"


# ── Mock response helpers ──────────────────────────────────────────────

def _mock_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    response.stop_reason = "end_turn"
    return response


MOCK_STRUCTURED = json.dumps({
    "contact": {"name": "Jeremy Springston", "email": "jeremy@example.com"},
    "summary": "AI/ML Engineer with 20+ years of leadership experience.",
    "experience": [
        {
            "section_type": "experience",
            "raw_text": "Booz Allen Hamilton, AI/ML Engineer 3",
            "bullets": ["Coordinating engineering decisions for PEO IWS 11.0"],
        }
    ],
    "skills": ["Python", "PyTorch", "RAG"],
    "education": [
        {"section_type": "education", "raw_text": "MS Johns Hopkins, Applied Mathematics 2021"}
    ],
    "certifications": [],
})

MOCK_STYLE = json.dumps({
    "formality_level": "formal",
    "sentence_length": "mixed",
    "structure_tendency": "action_first",
    "quantification_habit": "frequent",
    "vocabulary_register": "Technical, defense sector jargon",
})

MOCK_GAPS = json.dumps({
    "gaps": [
        {
            "severity": "high",
            "category": "missing_keywords",
            "description": "No AWS/Azure mentioned",
            "suggested_action": "Add cloud platform experience",
        }
    ],
    "jd_provided": True,
})

MOCK_INTEL = json.dumps({
    "role_category": "AI/ML Engineer",
    "industry": "Defense",
    "week": "2026-W12",
    "what_recruiters_reward": ["quantified impact"],
    "what_recruiters_skip": ["generic summaries"],
    "red_flags": ["typos"],
    "format_preferences": ["one page"],
    "current_ats_notes": ["standard headings"],
    "source_credibility_notes": "Verified recruiters",
    "legs_populated": ["linkedin"],
})

MOCK_REWRITE = json.dumps({
    "contact": {"name": "Jeremy Springston", "email": "jeremy@example.com"},
    "summary": "AI/ML Engineer with 20+ years of leadership experience.",
    "experience": [
        {
            "section_type": "experience",
            "raw_text": "Booz Allen Hamilton, AI/ML Engineer 3",
            "bullets": ["Led engineering decisions across 12 systems for PEO IWS 11.0"],
        }
    ],
    "skills": ["Python", "PyTorch", "RAG", "AWS"],
    "education": [
        {"section_type": "education", "raw_text": "MS Johns Hopkins, Applied Mathematics 2021"}
    ],
    "certifications": [],
    "rewrite_level_used": "edit",
    "change_log": ["Added quantification and AWS keyword"],
})

MOCK_KEYWORDS = json.dumps({
    "keywords": ["python", "aws", "azure", "sql", "docker"],
})


# ── Mocked end-to-end test ─────────────────────────────────────────────

class TestPipelineEndToEndMocked:
    """Full pipeline with mocked Claude calls — runs in default test suite."""

    def test_full_pipeline_mocked(self):
        """Walk through all 7 stages with mocked responses."""
        if not DOCX_PATH.exists():
            pytest.skip("DOCX fixture not available")

        # Stage 1: Parse
        raw_text = parse_docx(DOCX_PATH.read_bytes())
        assert "Alex Morgan" in raw_text
        assert len(raw_text) > 200

        jd = JD_PATH.read_text(encoding="utf-8") if JD_PATH.exists() else None

        # Stage 2+3+4+5+6: Mocked Claude calls
        # We track call order to return different responses
        call_count = {"n": 0}
        responses = [
            MOCK_STRUCTURED,  # structure_resume
            MOCK_INTEL,       # distill_intelligence
            MOCK_STYLE,       # extract_style
            MOCK_GAPS,        # analyze_gaps
            MOCK_REWRITE,     # rewrite_resume
            MOCK_KEYWORDS,    # score_keywords
        ]

        def mock_create(**kwargs):
            idx = min(call_count["n"], len(responses) - 1)
            call_count["n"] += 1
            return _mock_response(responses[idx])

        with patch("modules.resume.structurer.anthropic.Anthropic") as m1, \
             patch("modules.intelligence.distiller.anthropic.Anthropic") as m2, \
             patch("modules.resume.style.anthropic.Anthropic") as m3, \
             patch("modules.resume.analyzer.anthropic.Anthropic") as m4, \
             patch("modules.resume.rewriter.anthropic.Anthropic") as m5, \
             patch("modules.scoring.keyword_match.anthropic.Anthropic") as m6, \
             patch("modules.intelligence.distiller.get_cached_brief", return_value=None), \
             patch("modules.intelligence.distiller.store_brief"), \
             patch("modules.intelligence.distiller.fetch_intelligence") as mock_fetch:

            # Set up mock clients
            for mock_cls in [m1, m2, m3, m4, m5, m6]:
                client = MagicMock()
                mock_cls.return_value = client
                client.messages.create.side_effect = mock_create

            mock_fetch.return_value = MagicMock(
                linkedin=["some content"], reddit=[], broad=[]
            )

            # Stage 2: Structure
            resume = structure_resume(raw_text)
            assert isinstance(resume, ResumeSchema)
            assert resume.contact["name"] == "Jeremy Springston"

            # Stage 3: Intelligence
            intel = distill_intelligence("AI/ML Engineer", "Defense")
            assert isinstance(intel, IntelligenceBrief)

            # Stage 4: Style
            style = extract_style(raw_text)
            assert isinstance(style, StyleProfile)

            # Stage 5: Gap Analysis
            gaps = analyze_gaps(resume, job_posting=jd, intelligence_brief=intel)
            assert isinstance(gaps, GapReport)
            assert len(gaps.gaps) > 0

            # Stage 6: Rewrite
            revised = rewrite_resume(resume, style, gaps, level="edit")
            assert isinstance(revised, RevisedResumeSchema)
            assert len(revised.change_log) > 0

            # Stage 7: Keyword Scoring
            if jd:
                report = score_keywords(revised, jd)
                assert isinstance(report, KeywordReport)
                assert report.match_pct >= 0

            # Stage 8: Render
            docx_bytes = render_docx(revised)
            assert isinstance(docx_bytes, bytes)
            assert len(docx_bytes) > 0

    def test_pipeline_without_jd(self):
        """Pipeline works without a job description."""
        if not DOCX_PATH.exists():
            pytest.skip("DOCX fixture not available")

        raw_text = parse_docx(DOCX_PATH.read_bytes())

        mock_gaps_no_jd = json.dumps({
            "gaps": [
                {
                    "severity": "low",
                    "category": "format_issues",
                    "description": "Summary could be more targeted",
                    "suggested_action": "Tailor to role type",
                }
            ],
            "jd_provided": False,
        })

        responses = [MOCK_STRUCTURED, MOCK_STYLE, mock_gaps_no_jd, MOCK_REWRITE]
        call_count = {"n": 0}

        def mock_create(**kwargs):
            idx = min(call_count["n"], len(responses) - 1)
            call_count["n"] += 1
            return _mock_response(responses[idx])

        with patch("modules.resume.structurer.anthropic.Anthropic") as m1, \
             patch("modules.resume.style.anthropic.Anthropic") as m2, \
             patch("modules.resume.analyzer.anthropic.Anthropic") as m3, \
             patch("modules.resume.rewriter.anthropic.Anthropic") as m4:

            for mock_cls in [m1, m2, m3, m4]:
                client = MagicMock()
                mock_cls.return_value = client
                client.messages.create.side_effect = mock_create

            resume = structure_resume(raw_text)
            style = extract_style(raw_text)
            gaps = analyze_gaps(resume, job_posting=None, intelligence_brief=None)

            assert gaps.jd_provided is False

            revised = rewrite_resume(resume, style, gaps, level="edit")
            docx_bytes = render_docx(revised)

            assert len(docx_bytes) > 0

    def test_pipeline_graceful_degradation(self):
        """Pipeline handles intelligence fetch failure gracefully."""
        if not DOCX_PATH.exists():
            pytest.skip("DOCX fixture not available")

        raw_text = parse_docx(DOCX_PATH.read_bytes())

        responses = [MOCK_STRUCTURED, MOCK_STYLE, MOCK_GAPS, MOCK_REWRITE]
        call_count = {"n": 0}

        def mock_create(**kwargs):
            idx = min(call_count["n"], len(responses) - 1)
            call_count["n"] += 1
            return _mock_response(responses[idx])

        with patch("modules.resume.structurer.anthropic.Anthropic") as m1, \
             patch("modules.resume.style.anthropic.Anthropic") as m2, \
             patch("modules.resume.analyzer.anthropic.Anthropic") as m3, \
             patch("modules.resume.rewriter.anthropic.Anthropic") as m4, \
             patch("modules.intelligence.distiller.get_cached_brief", return_value=None), \
             patch("modules.intelligence.distiller.fetch_intelligence") as mock_fetch:

            for mock_cls in [m1, m2, m3, m4]:
                client = MagicMock()
                mock_cls.return_value = client
                client.messages.create.side_effect = mock_create

            # Intelligence fetch returns empty — all legs fail
            mock_fetch.return_value = MagicMock(linkedin=[], reddit=[], broad=[])

            resume = structure_resume(raw_text)
            intel = distill_intelligence("AI/ML Engineer", "Defense")
            assert intel is None  # Graceful degradation

            style = extract_style(raw_text)
            jd = JD_PATH.read_text(encoding="utf-8") if JD_PATH.exists() else None
            gaps = analyze_gaps(resume, job_posting=jd, intelligence_brief=None)
            revised = rewrite_resume(resume, style, gaps, level="edit")
            docx_bytes = render_docx(revised)

            assert len(docx_bytes) > 0


# ── Live end-to-end test ───────────────────────────────────────────────

@pytest.mark.integration
class TestPipelineEndToEndLive:
    """Full pipeline with live API calls — only run with: pytest -m integration"""

    @pytest.fixture(autouse=True)
    def _clean_cache(self):
        clear_cache()
        yield
        clear_cache()

    def test_full_pipeline_live(self):
        """Complete pipeline: parse → structure → style → gaps → rewrite → score → render."""
        if not DOCX_PATH.exists():
            pytest.skip("DOCX fixture not available")

        jd = JD_PATH.read_text(encoding="utf-8") if JD_PATH.exists() else None

        # Stage 1: Parse
        raw_text = parse_resume("sample_resume.docx", DOCX_PATH.read_bytes())
        assert len(raw_text) > 200

        # Stage 2: Structure
        resume = structure_resume(raw_text)
        assert isinstance(resume, ResumeSchema)
        assert len(resume.experience) > 0

        # Stage 3: Intelligence (may return None)
        intel = distill_intelligence("AI/ML Engineer", "Defense / Government")

        # Stage 4: Style
        style = extract_style(raw_text)
        assert isinstance(style, StyleProfile)

        # Stage 5: Gap Analysis
        gaps = analyze_gaps(resume, job_posting=jd, intelligence_brief=intel)
        assert isinstance(gaps, GapReport)

        # Stage 6: Rewrite (Level 2 — edit)
        revised = rewrite_resume(
            resume, style, gaps,
            level="edit",
            intelligence_brief=intel,
        )
        assert isinstance(revised, RevisedResumeSchema)
        assert revised.rewrite_level_used == "edit"
        assert len(revised.change_log) > 0

        # Stage 7: Keyword Scoring
        if jd:
            report = score_keywords(revised, jd)
            assert isinstance(report, KeywordReport)
            assert report.match_pct > 0  # Should match at least some keywords
            assert len(report.present_terms) > 0

        # Stage 8: Render DOCX
        docx_bytes = render_docx(revised)
        assert isinstance(docx_bytes, bytes)
        assert len(docx_bytes) > 1000  # Real DOCX should be > 1KB

        # Verify DOCX is valid
        from docx import Document
        import io
        doc = Document(io.BytesIO(docx_bytes))
        all_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Alex Morgan" in all_text or "Morgan" in all_text
