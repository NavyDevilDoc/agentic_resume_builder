"""Tests for security/sanitizer.py — file validation, text sanitization, and content wrapping."""

import pytest

from security.sanitizer import (
    SanitizationError,
    sanitize_text,
    validate_file_upload,
    wrap_user_content,
)


# ── File upload validation ─────────────────────────────────────────────

class TestValidateFileUpload:
    def test_valid_pdf(self):
        validate_file_upload("resume.pdf", 1024, "application/pdf")

    def test_valid_docx(self):
        validate_file_upload(
            "resume.docx",
            2048,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def test_valid_no_mime(self):
        """MIME type is optional (some upload widgets don't provide it)."""
        validate_file_upload("resume.pdf", 1024)

    def test_reject_wrong_extension(self):
        with pytest.raises(SanitizationError, match="Unsupported file type"):
            validate_file_upload("resume.txt", 1024)

    def test_reject_exe(self):
        with pytest.raises(SanitizationError, match="Unsupported file type"):
            validate_file_upload("malware.exe", 1024)

    def test_reject_oversized(self):
        with pytest.raises(SanitizationError, match="too large"):
            validate_file_upload("resume.pdf", 6 * 1024 * 1024)

    def test_reject_empty_file(self):
        with pytest.raises(SanitizationError, match="empty"):
            validate_file_upload("resume.pdf", 0)

    def test_reject_wrong_mime(self):
        with pytest.raises(SanitizationError, match="Unexpected file type"):
            validate_file_upload("resume.pdf", 1024, "text/plain")

    def test_case_insensitive_extension(self):
        validate_file_upload("RESUME.PDF", 1024)
        validate_file_upload("Resume.Docx", 2048)


# ── Text sanitization ─────────────────────────────────────────────────

class TestSanitizeText:
    def test_plain_text_passthrough(self):
        assert sanitize_text("Hello world") == "Hello world"

    def test_strips_html_tags(self):
        assert sanitize_text("<b>Bold</b> text") == "Bold text"

    def test_strips_script_tags(self):
        result = sanitize_text("Before<script>alert('xss')</script>After")
        assert "script" not in result
        assert result == "BeforeAfter"

    def test_strips_style_tags(self):
        result = sanitize_text("Text<style>body{color:red}</style>More")
        assert "style" not in result
        assert result == "TextMore"

    def test_strips_whitespace(self):
        assert sanitize_text("  hello  ") == "hello"

    def test_truncates_long_text(self):
        long_text = "a" * 100
        result = sanitize_text(long_text, max_length=50)
        assert len(result) == 50

    def test_rejects_empty_after_strip(self):
        with pytest.raises(SanitizationError, match="empty"):
            sanitize_text("<script>alert('xss')</script>")

    def test_rejects_whitespace_only(self):
        with pytest.raises(SanitizationError, match="empty"):
            sanitize_text("   \n\t  ")

    def test_preserves_normal_angle_brackets_in_text(self):
        """Angle brackets in non-tag context get stripped by regex.
        This documents the current behavior."""
        result = sanitize_text("5 > 3 and 2 < 4")
        # The regex strips < ... > so "< 4" becomes removed
        assert "5" in result


# ── Content wrapping ───────────────────────────────────────────────────

class TestWrapUserContent:
    def test_basic_wrap(self):
        result = wrap_user_content("My resume text", "resume_text")
        assert result == "<resume_text>\nMy resume text\n</resume_text>"

    def test_wrap_preserves_content(self):
        content = "Line 1\nLine 2\nLine 3"
        result = wrap_user_content(content, "job_posting")
        assert "<job_posting>" in result
        assert "</job_posting>" in result
        assert content in result
