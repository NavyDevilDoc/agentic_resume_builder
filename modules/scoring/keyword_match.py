"""JD keyword scoring to produce a KeywordReport.

Extracts keywords from the job description via Claude, then compares
against the revised resume to compute match percentage.
This is NOT an ATS compliance checker — it scores keyword relevance only.
"""

import json
import logging
import os

import anthropic

from models.schemas import KeywordReport, RevisedResumeSchema
from modules.llm_helpers import CLAUDE_MODEL, extract_json
from prompts.scoring import KEYWORD_EXTRACTION_SYSTEM, KEYWORD_EXTRACTION_USER

logger = logging.getLogger(__name__)


class ScoringError(Exception):
    """Raised when keyword scoring fails."""


def _extract_jd_keywords(job_posting: str) -> list[str]:
    """Extract keywords from a job description via Claude.

    Args:
        job_posting: Raw job description text.

    Returns:
        List of lowercase keywords.

    Raises:
        ScoringError: If extraction fails.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    user_prompt = KEYWORD_EXTRACTION_USER.format(job_posting=job_posting)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            system=KEYWORD_EXTRACTION_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as e:
        logger.error("Claude API error during keyword extraction: %s", e)
        raise ScoringError(
            "Failed to extract job description keywords. Please try again."
        ) from e

    raw_content = response.content[0].text.strip()

    try:
        data = extract_json(raw_content)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse keyword extraction response: %s", e)
        raise ScoringError(
            "AI returned an invalid keyword extraction. Please try again."
        ) from e

    keywords = data.get("keywords", [])
    # Normalize to lowercase
    return [k.lower().strip() for k in keywords if k.strip()]


def _build_resume_text(resume: RevisedResumeSchema) -> str:
    """Flatten a resume schema into searchable text."""
    parts = []

    if resume.summary:
        parts.append(resume.summary)

    for section in resume.experience:
        parts.append(section.raw_text)
        if section.bullets:
            parts.extend(section.bullets)

    parts.extend(resume.skills)

    for section in resume.education:
        parts.append(section.raw_text)

    parts.extend(resume.certifications)

    return " ".join(parts).lower()


def score_keywords(
    resume: RevisedResumeSchema,
    job_posting: str,
) -> KeywordReport:
    """Score keyword overlap between revised resume and job description.

    Args:
        resume: The revised resume to score.
        job_posting: Raw job description text.

    Returns:
        KeywordReport with match percentage, present terms, missing terms.

    Raises:
        ScoringError: If keyword extraction fails.
    """
    jd_keywords = _extract_jd_keywords(job_posting)

    if not jd_keywords:
        logger.warning("No keywords extracted from job description")
        return KeywordReport(
            match_pct=0.0,
            present_terms=[],
            missing_terms=[],
        )

    resume_text = _build_resume_text(resume)

    present = []
    missing = []

    for keyword in jd_keywords:
        if keyword in resume_text:
            present.append(keyword)
        else:
            missing.append(keyword)

    match_pct = (len(present) / len(jd_keywords)) * 100 if jd_keywords else 0.0

    logger.info(
        "Keyword scoring: %.1f%% match (%d/%d present, %d missing)",
        match_pct,
        len(present),
        len(jd_keywords),
        len(missing),
    )

    return KeywordReport(
        match_pct=round(match_pct, 1),
        present_terms=present,
        missing_terms=missing,
    )
