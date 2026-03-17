"""Integration tests for M1: parser + structurer with live Claude API.

Only run with: pytest -m integration
"""

from pathlib import Path

import pytest

from models.schemas import ResumeSchema
from modules.resume.parser import parse_docx, parse_pdf, parse_resume
from modules.resume.structurer import structure_resume

pytestmark = pytest.mark.integration

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "sample_resumes"


class TestParserStructurerLive:
    def test_docx_parse_and_structure(self):
        docx_path = FIXTURES_DIR / "sample_resume.docx"
        if not docx_path.exists():
            pytest.skip("DOCX fixture not available")

        # Parse
        text = parse_docx(docx_path.read_bytes())
        assert "Alex Morgan" in text
        assert len(text) > 200

        # Structure via live Claude
        schema = structure_resume(text)

        assert isinstance(schema, ResumeSchema)
        assert schema.contact.get("name") is not None
        assert len(schema.experience) > 0
        assert len(schema.skills) > 0
        assert len(schema.education) > 0

        # Verify key content was extracted
        all_text = " ".join(
            s.raw_text for s in schema.experience
        ).lower()
        assert "apex defense" in all_text or "navy" in all_text

    def test_pdf_parse_and_structure(self):
        pdf_path = FIXTURES_DIR / "sample_resume.pdf"
        if not pdf_path.exists():
            pytest.skip("PDF fixture not available")

        text = parse_pdf(pdf_path.read_bytes())
        assert "Jane Doe" in text

        schema = structure_resume(text)

        assert isinstance(schema, ResumeSchema)
        assert len(schema.experience) > 0

    def test_full_router_to_structure(self):
        """End-to-end: parse_resume() -> structure_resume()"""
        docx_path = FIXTURES_DIR / "sample_resume.docx"
        if not docx_path.exists():
            pytest.skip("DOCX fixture not available")

        text = parse_resume("sample_resume.docx", docx_path.read_bytes())
        schema = structure_resume(text)

        assert isinstance(schema, ResumeSchema)
        assert schema.summary is not None
