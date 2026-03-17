"""Schema validation tests: confirm all Pydantic models accept valid data and reject malformed data."""

import pytest
from pydantic import ValidationError

from models.schemas import (
    GapItem,
    GapReport,
    IntelligenceBrief,
    KeywordReport,
    ResumeSchema,
    ResumeSection,
    RevisedResumeSchema,
    StyleProfile,
    UserInput,
)


# ── UserInput ──────────────────────────────────────────────────────────

class TestUserInput:
    def test_valid_full(self):
        ui = UserInput(
            resume_text="Some resume content",
            job_posting="Some job posting",
            role_category="AI/ML Engineer",
            industry="Defense",
            voice_sample="I like to write concisely.",
        )
        assert ui.resume_text == "Some resume content"
        assert ui.job_posting == "Some job posting"
        assert ui.voice_sample == "I like to write concisely."

    def test_valid_minimal(self):
        ui = UserInput(
            resume_text="Resume text here",
            role_category="Software Engineer",
            industry="Tech",
        )
        assert ui.job_posting is None
        assert ui.voice_sample is None

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            UserInput(
                resume_text="Resume",
                # missing role_category and industry
            )

    def test_empty_resume_text_allowed(self):
        """Pydantic allows empty strings; sanitizer enforces non-empty."""
        ui = UserInput(
            resume_text="",
            role_category="Engineer",
            industry="Tech",
        )
        assert ui.resume_text == ""


# ── StyleProfile ───────────────────────────────────────────────────────

class TestStyleProfile:
    def test_valid(self):
        sp = StyleProfile(
            formality_level="formal",
            sentence_length="mixed",
            structure_tendency="action_first",
            quantification_habit="frequent",
            vocabulary_register="Technical, acronym-heavy",
        )
        assert sp.formality_level == "formal"

    def test_invalid_literal(self):
        with pytest.raises(ValidationError):
            StyleProfile(
                formality_level="super_casual",  # not a valid literal
                sentence_length="mixed",
                structure_tendency="action_first",
                quantification_habit="frequent",
                vocabulary_register="Casual",
            )

    def test_missing_vocabulary_register(self):
        with pytest.raises(ValidationError):
            StyleProfile(
                formality_level="neutral",
                sentence_length="short",
                structure_tendency="mixed",
                quantification_habit="rare",
                # missing vocabulary_register
            )


# ── IntelligenceBrief ──────────────────────────────────────────────────

class TestIntelligenceBrief:
    def test_valid_full(self):
        ib = IntelligenceBrief(
            role_category="AI/ML Engineer",
            industry="Defense",
            week="2026-W11",
            what_recruiters_reward=["quantified impact"],
            what_recruiters_skip=["generic summaries"],
            red_flags=["typos"],
            format_preferences=["one page"],
            current_ats_notes=["use standard headings"],
            source_credibility_notes="Mix of verified recruiters",
            legs_populated=["linkedin", "reddit"],
        )
        assert ib.week == "2026-W11"
        assert len(ib.legs_populated) == 2

    def test_valid_minimal_defaults(self):
        ib = IntelligenceBrief(
            role_category="Data Scientist",
            industry="Finance",
            week="2026-W11",
        )
        assert ib.what_recruiters_reward == []
        assert ib.legs_populated == []
        assert ib.source_credibility_notes == ""

    def test_invalid_leg(self):
        with pytest.raises(ValidationError):
            IntelligenceBrief(
                role_category="Engineer",
                industry="Tech",
                week="2026-W11",
                legs_populated=["twitter"],  # not a valid literal
            )


# ── ResumeSection & ResumeSchema ───────────────────────────────────────

class TestResumeSchema:
    def test_valid_section(self):
        section = ResumeSection(
            section_type="experience",
            raw_text="Worked at Acme Corp",
            bullets=["Built things", "Led teams"],
        )
        assert len(section.bullets) == 2

    def test_section_no_bullets(self):
        section = ResumeSection(
            section_type="education",
            raw_text="BS Computer Science",
        )
        assert section.bullets is None

    def test_valid_resume(self):
        resume = ResumeSchema(
            contact={"name": "Jane Doe", "email": "jane@example.com"},
            summary="Experienced engineer",
            experience=[
                ResumeSection(
                    section_type="experience",
                    raw_text="Acme Corp",
                    bullets=["Did work"],
                )
            ],
            skills=["Python", "ML"],
            education=[
                ResumeSection(
                    section_type="education",
                    raw_text="MIT",
                )
            ],
            certifications=["AWS SAA"],
        )
        assert resume.contact["name"] == "Jane Doe"
        assert len(resume.experience) == 1

    def test_empty_resume_defaults(self):
        resume = ResumeSchema()
        assert resume.contact == {}
        assert resume.summary is None
        assert resume.experience == []
        assert resume.skills == []


# ── GapItem & GapReport ────────────────────────────────────────────────

class TestGapReport:
    def test_valid_gap_item(self):
        item = GapItem(
            severity="high",
            category="Missing keywords",
            description="Resume lacks cloud infrastructure terms",
            suggested_action="Add AWS/Azure experience to skills section",
        )
        assert item.severity == "high"

    def test_invalid_severity(self):
        with pytest.raises(ValidationError):
            GapItem(
                severity="critical",  # not a valid literal
                category="Format",
                description="Bad format",
                suggested_action="Fix it",
            )

    def test_valid_gap_report(self):
        report = GapReport(
            gaps=[
                GapItem(
                    severity="medium",
                    category="Weak bullets",
                    description="Bullets lack quantification",
                    suggested_action="Add metrics",
                )
            ],
            jd_provided=True,
        )
        assert report.jd_provided is True
        assert len(report.gaps) == 1

    def test_missing_jd_provided(self):
        with pytest.raises(ValidationError):
            GapReport(gaps=[])  # missing jd_provided


# ── KeywordReport ──────────────────────────────────────────────────────

class TestKeywordReport:
    def test_valid(self):
        kr = KeywordReport(
            match_pct=72.5,
            present_terms=["Python", "AI"],
            missing_terms=["Java", "Azure"],
        )
        assert kr.match_pct == 72.5

    def test_defaults(self):
        kr = KeywordReport(match_pct=0.0)
        assert kr.present_terms == []
        assert kr.missing_terms == []


# ── RevisedResumeSchema ────────────────────────────────────────────────

class TestRevisedResumeSchema:
    def test_valid(self):
        revised = RevisedResumeSchema(
            contact={"name": "Jane Doe"},
            rewrite_level_used="edit",
            change_log=["Strengthened bullet 1 with metrics"],
        )
        assert revised.rewrite_level_used == "edit"
        assert len(revised.change_log) == 1
        # Inherits ResumeSchema defaults
        assert revised.skills == []

    def test_invalid_rewrite_level(self):
        with pytest.raises(ValidationError):
            RevisedResumeSchema(
                contact={},
                rewrite_level_used="partial",  # not valid
                change_log=[],
            )

    def test_missing_rewrite_level(self):
        with pytest.raises(ValidationError):
            RevisedResumeSchema(
                contact={},
                change_log=[],
            )
