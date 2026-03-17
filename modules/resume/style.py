"""ResumeSchema + voice sample to StyleProfile extraction via Claude.

Analyzes existing resume text (and optional voice sample) to characterize
the author's writing style. The resulting StyleProfile is used as a
constraint during rewriting, not a content source.
"""

import json
import logging
import os

import anthropic

from models.schemas import StyleProfile
from modules.llm_helpers import CLAUDE_MODEL, extract_json
from prompts.structuring import (
    STYLE_EXTRACTION_SYSTEM,
    STYLE_EXTRACTION_USER,
    VOICE_SAMPLE_BLOCK,
)

logger = logging.getLogger(__name__)


class StyleExtractionError(Exception):
    """Raised when style extraction fails."""


def extract_style(
    resume_text: str, voice_sample: str | None = None
) -> StyleProfile:
    """Analyze resume text and optional voice sample to produce a StyleProfile.

    Args:
        resume_text: Raw text extracted from the resume.
        voice_sample: Optional user-provided writing sample.

    Returns:
        Validated StyleProfile instance.

    Raises:
        StyleExtractionError: If the API call fails or response cannot be parsed.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    voice_block = ""
    if voice_sample:
        voice_block = VOICE_SAMPLE_BLOCK.format(voice_sample=voice_sample)

    user_prompt = STYLE_EXTRACTION_USER.format(
        resume_text=resume_text,
        voice_sample_block=voice_block,
    )

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system=STYLE_EXTRACTION_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as e:
        logger.error("Claude API error during style extraction: %s", e)
        raise StyleExtractionError(
            "Failed to analyze writing style. Please try again."
        ) from e

    raw_content = response.content[0].text.strip()

    try:
        data = extract_json(raw_content)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse style response as JSON: %s", e)
        raise StyleExtractionError(
            "AI returned an invalid style analysis. Please try again."
        ) from e

    try:
        profile = StyleProfile.model_validate(data)
    except Exception as e:
        logger.error("Style data failed schema validation: %s", e)
        raise StyleExtractionError(
            "AI style analysis did not match expected format. Please try again."
        ) from e

    logger.info(
        "Style extracted: formality=%s, structure=%s, quantification=%s",
        profile.formality_level,
        profile.structure_tendency,
        profile.quantification_habit,
    )
    return profile
