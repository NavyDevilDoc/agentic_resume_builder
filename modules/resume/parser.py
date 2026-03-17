"""PDF/DOCX file parsing to raw text extraction.

Uses pdfminer.six for PDF and python-docx for DOCX.
Extracts raw text only — no layout reconstruction.
"""

import io
import logging
from pathlib import Path

from docx import Document
from pdfminer.high_level import extract_text as pdf_extract_text

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Raised when a resume file cannot be parsed."""


def parse_pdf(file_bytes: bytes) -> str:
    """Extract raw text from a PDF file.

    Args:
        file_bytes: Raw bytes of the PDF file.

    Returns:
        Extracted text content.

    Raises:
        ParseError: If the PDF cannot be read or contains no extractable text.
    """
    try:
        text = pdf_extract_text(io.BytesIO(file_bytes))
    except Exception as e:
        logger.error("PDF parsing failed: %s", type(e).__name__)
        raise ParseError(f"Could not read PDF file: {e}") from e

    text = text.strip()
    if not text:
        raise ParseError(
            "PDF file contains no extractable text. "
            "It may be a scanned image — please upload a text-based PDF or DOCX."
        )
    return text


def parse_docx(file_bytes: bytes) -> str:
    """Extract raw text from a DOCX file.

    Args:
        file_bytes: Raw bytes of the DOCX file.

    Returns:
        Extracted text content (paragraphs joined by newlines).

    Raises:
        ParseError: If the DOCX cannot be read or contains no text.
    """
    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        logger.error("DOCX parsing failed: %s", type(e).__name__)
        raise ParseError(f"Could not read DOCX file: {e}") from e

    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)

    if not text.strip():
        raise ParseError("DOCX file contains no text content.")

    return text


def parse_resume(file_name: str, file_bytes: bytes) -> str:
    """Route to the correct parser based on file extension.

    Args:
        file_name: Original filename (used to determine format).
        file_bytes: Raw bytes of the uploaded file.

    Returns:
        Extracted raw text.

    Raises:
        ParseError: If the file type is unsupported or parsing fails.
    """
    ext = Path(file_name).suffix.lower()

    if ext == ".pdf":
        logger.info("Parsing PDF: %s", file_name)
        return parse_pdf(file_bytes)
    elif ext == ".docx":
        logger.info("Parsing DOCX: %s", file_name)
        return parse_docx(file_bytes)
    else:
        raise ParseError(f"Unsupported file type: {ext}")
