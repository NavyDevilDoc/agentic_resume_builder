"""Tests for resume file parsing (PDF/DOCX to raw text)."""

from pathlib import Path

import pytest

from modules.resume.parser import ParseError, parse_docx, parse_pdf, parse_resume

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "sample_resumes"


# ── DOCX parsing ───────────────────────────────────────────────────────

class TestParseDocx:
    def test_springston_docx(self):
        """Parse the real DOCX test fixture."""
        docx_path = FIXTURES_DIR / "sample_resume.docx"
        if not docx_path.exists():
            pytest.skip("DOCX fixture not available")

        file_bytes = docx_path.read_bytes()
        text = parse_docx(file_bytes)

        assert len(text) > 100
        assert "Alex Morgan" in text
        # Verify key sections are extracted
        assert "Experience" in text or "experience" in text.lower()
        assert "Education" in text or "education" in text.lower()

    def test_empty_docx_raises(self):
        """A DOCX with no text content should raise ParseError."""
        from docx import Document
        import io

        doc = Document()
        buf = io.BytesIO()
        doc.save(buf)

        with pytest.raises(ParseError, match="no text content"):
            parse_docx(buf.getvalue())

    def test_invalid_bytes_raises(self):
        """Random bytes should raise ParseError."""
        with pytest.raises(ParseError, match="Could not read DOCX"):
            parse_docx(b"this is not a docx file")


# ── PDF parsing ────────────────────────────────────────────────────────

class TestParsePdf:
    def test_sample_pdf(self):
        """Parse the generated sample PDF fixture."""
        pdf_path = FIXTURES_DIR / "sample_resume.pdf"
        if not pdf_path.exists():
            pytest.skip("PDF fixture not available")

        file_bytes = pdf_path.read_bytes()
        text = parse_pdf(file_bytes)

        assert len(text) > 50
        assert "Jane Doe" in text
        assert "Experience" in text

    def test_invalid_bytes_raises(self):
        """Random bytes should raise ParseError."""
        with pytest.raises(ParseError, match="Could not read PDF"):
            parse_pdf(b"not a pdf at all")


# ── Router function ───────────────────────────────────────────────────

class TestParseResume:
    def test_routes_docx(self):
        docx_path = FIXTURES_DIR / "sample_resume.docx"
        if not docx_path.exists():
            pytest.skip("DOCX fixture not available")

        text = parse_resume("resume.docx", docx_path.read_bytes())
        assert "Alex Morgan" in text

    def test_routes_pdf(self):
        pdf_path = FIXTURES_DIR / "sample_resume.pdf"
        if not pdf_path.exists():
            pytest.skip("PDF fixture not available")

        text = parse_resume("resume.pdf", pdf_path.read_bytes())
        assert "Jane Doe" in text

    def test_unsupported_extension(self):
        with pytest.raises(ParseError, match="Unsupported file type"):
            parse_resume("resume.txt", b"some text")

    def test_case_insensitive_extension(self):
        pdf_path = FIXTURES_DIR / "sample_resume.pdf"
        if not pdf_path.exists():
            pytest.skip("PDF fixture not available")

        text = parse_resume("RESUME.PDF", pdf_path.read_bytes())
        assert "Jane Doe" in text
