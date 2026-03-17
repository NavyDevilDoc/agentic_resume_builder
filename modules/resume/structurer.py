"""Raw resume text to structured ResumeSchema via Claude API.

Sends raw text to Claude with the structuring prompt and parses
the JSON response into a validated ResumeSchema.
"""

import json
import logging
import os

import anthropic

from models.schemas import ResumeSchema
from modules.llm_helpers import CLAUDE_MODEL, extract_json
from prompts.structuring import RESUME_STRUCTURING_SYSTEM, RESUME_STRUCTURING_USER

logger = logging.getLogger(__name__)


class StructuringError(Exception):
    """Raised when resume structuring fails."""


def structure_resume(resume_text: str) -> ResumeSchema:
    """Convert raw resume text into a structured ResumeSchema.

    Args:
        resume_text: Raw text extracted from the resume file.

    Returns:
        Validated ResumeSchema instance.

    Raises:
        StructuringError: If the API call fails or response cannot be parsed.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    user_prompt = RESUME_STRUCTURING_USER.format(resume_text=resume_text)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=RESUME_STRUCTURING_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as e:
        logger.error("Claude API error during structuring: %s", e)
        raise StructuringError(
            "Failed to contact the AI service. Please try again."
        ) from e

    raw_content = response.content[0].text.strip()

    try:
        data = extract_json(raw_content)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse structuring response as JSON: %s", e)
        raise StructuringError(
            "AI returned an invalid response. Please try again."
        ) from e

    try:
        schema = ResumeSchema.model_validate(data)
    except Exception as e:
        logger.error("Structured data failed schema validation: %s", e)
        raise StructuringError(
            "AI response did not match expected format. Please try again."
        ) from e

    logger.info(
        "Resume structured: %d experience sections, %d skills, %d education sections",
        len(schema.experience),
        len(schema.skills),
        len(schema.education),
    )
    return schema
