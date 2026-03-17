"""Input validation and sanitization helpers for all pipeline stages."""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Constraints
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_TEXT_LENGTH = 50_000  # characters
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_EXTENSIONS = {".pdf", ".docx"}

# Minimal HTML/script tag pattern for stripping
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)
_SCRIPT_RE = re.compile(
    r"<script[\s\S]*?</script>", re.DOTALL | re.IGNORECASE
)
_STYLE_RE = re.compile(
    r"<style[\s\S]*?</style>", re.DOTALL | re.IGNORECASE
)


class SanitizationError(Exception):
    """Raised when input fails validation."""


def validate_file_upload(
    file_name: str,
    file_size: int,
    file_content_type: str | None = None,
) -> None:
    """Validate an uploaded file before any processing.

    Args:
        file_name: Original filename from the upload.
        file_size: Size in bytes.
        file_content_type: MIME type reported by the upload widget.

    Raises:
        SanitizationError: If the file fails any validation check.
    """
    # Extension check
    ext = Path(file_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise SanitizationError(
            f"Unsupported file type '{ext}'. Please upload a PDF or DOCX file."
        )

    # Size check
    if file_size > MAX_FILE_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        raise SanitizationError(
            f"File is too large ({size_mb:.1f} MB). Maximum allowed size is 5 MB."
        )

    if file_size == 0:
        raise SanitizationError("File is empty.")

    # MIME type check (if provided by the upload widget)
    if file_content_type and file_content_type not in ALLOWED_MIME_TYPES:
        logger.warning(
            "MIME type mismatch: got %s for file %s",
            file_content_type,
            file_name,
        )
        raise SanitizationError(
            f"Unexpected file type '{file_content_type}'. "
            "Please upload a PDF or DOCX file."
        )


def sanitize_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """Strip HTML/script content and enforce length cap on pasted text.

    Args:
        text: Raw user-pasted text (job posting, voice sample, etc.).
        max_length: Maximum allowed character count.

    Returns:
        Cleaned, length-capped text.

    Raises:
        SanitizationError: If text is empty after sanitization.
    """
    # Remove script and style blocks first (before general tag strip)
    cleaned = _SCRIPT_RE.sub("", text)
    cleaned = _STYLE_RE.sub("", cleaned)
    cleaned = _HTML_TAG_RE.sub("", cleaned)

    # Normalize whitespace
    cleaned = cleaned.strip()

    if not cleaned:
        raise SanitizationError(
            "Text input is empty after removing HTML content."
        )

    # Length cap
    if len(cleaned) > max_length:
        logger.info(
            "Text input truncated from %d to %d characters",
            len(cleaned),
            max_length,
        )
        cleaned = cleaned[:max_length]

    return cleaned


def wrap_user_content(content: str, tag: str) -> str:
    """Wrap user-supplied content in XML delimiters for prompt injection defense.

    All user content entering LLM prompts must be wrapped with this function
    so it is treated as data, not instructions.

    Args:
        content: The user-supplied text.
        tag: The XML tag name (e.g., "resume_text", "job_posting").

    Returns:
        Content wrapped in XML tags.
    """
    return f"<{tag}>\n{content}\n</{tag}>"
