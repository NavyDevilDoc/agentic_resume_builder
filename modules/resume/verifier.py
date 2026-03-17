"""Rewrite verification: compare original vs revised resume for fabricated content.

Runs a lightweight Claude call to flag any content in the revised resume
that does not trace back to the original. Produces a VerificationReport
with categorized flags and severity levels.
"""

import json
import logging
import os

import anthropic

from models.schemas import ResumeSchema, RevisedResumeSchema, VerificationReport
from modules.llm_helpers import CLAUDE_MODEL, extract_json
from prompts.verification import VERIFICATION_SYSTEM, VERIFICATION_USER

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Raised when verification fails."""


def verify_rewrite(
    original: ResumeSchema,
    revised: RevisedResumeSchema,
) -> VerificationReport:
    """Compare original and revised resumes, flagging potential fabrications.

    Args:
        original: The original structured resume.
        revised: The revised resume after rewriting.

    Returns:
        VerificationReport with flags for any suspicious content.

    Raises:
        VerificationError: If the API call fails or response cannot be parsed.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    user_prompt = VERIFICATION_USER.format(
        original_json=original.model_dump_json(indent=2),
        revised_json=revised.model_dump_json(indent=2),
    )

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=VERIFICATION_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as e:
        logger.error("Claude API error during verification: %s", e)
        raise VerificationError(
            "Failed to verify rewrite. Please review changes manually."
        ) from e

    raw_content = response.content[0].text.strip()

    try:
        data = extract_json(raw_content)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse verification response: %s", e)
        raise VerificationError(
            "AI returned an invalid verification response."
        ) from e

    try:
        report = VerificationReport.model_validate(data)
    except Exception as e:
        logger.error("Verification data failed schema validation: %s", e)
        raise VerificationError(
            "AI verification did not match expected format."
        ) from e

    warnings = sum(1 for f in report.flags if f.severity == "warning")
    infos = sum(1 for f in report.flags if f.severity == "info")
    logger.info(
        "Verification complete: %d flags (%d warnings, %d info), clean=%s",
        len(report.flags),
        warnings,
        infos,
        report.verified_clean,
    )
    return report
