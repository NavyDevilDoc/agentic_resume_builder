"""Escalating rewrite engine: suggestions, edits, or full rewrite.

Three levels of intervention, all constrained by StyleProfile and
optionally informed by IntelligenceBrief and voice sample.
"""

import json
import logging
import os
from typing import Literal

import anthropic

from models.schemas import (
    GapReport,
    IntelligenceBrief,
    ResumeSchema,
    RevisedResumeSchema,
    StyleProfile,
)
from modules.llm_helpers import CLAUDE_MODEL, extract_json
from prompts.rewriting import (
    LEVEL1_SYSTEM,
    LEVEL1_USER,
    LEVEL2_SYSTEM,
    LEVEL2_USER,
    LEVEL3_SYSTEM,
    LEVEL3_USER,
    build_intelligence_block,
    build_style_constraint,
    build_voice_block,
)

logger = logging.getLogger(__name__)

RewriteLevel = Literal["suggestions", "edit", "full_rewrite"]

# Map level names to prompt pairs
_PROMPTS = {
    "suggestions": (LEVEL1_SYSTEM, LEVEL1_USER),
    "edit": (LEVEL2_SYSTEM, LEVEL2_USER),
    "full_rewrite": (LEVEL3_SYSTEM, LEVEL3_USER),
}


class RewriteError(Exception):
    """Raised when the rewrite engine fails."""


def rewrite_resume(
    resume: ResumeSchema,
    style_profile: StyleProfile,
    gap_report: GapReport,
    level: RewriteLevel = "suggestions",
    intelligence_brief: IntelligenceBrief | None = None,
    voice_sample: str | None = None,
) -> RevisedResumeSchema | dict:
    """Run the rewrite engine at the specified escalation level.

    Args:
        resume: Structured resume data.
        style_profile: Author's writing style constraints.
        gap_report: Identified gaps to address.
        level: Escalation level — "suggestions", "edit", or "full_rewrite".
        intelligence_brief: Recruiter intelligence (optional).
        voice_sample: Author's writing sample (optional).

    Returns:
        - For level "suggestions": a dict with suggestion structure
        - For levels "edit" and "full_rewrite": a RevisedResumeSchema

    Raises:
        RewriteError: If the API call fails or response cannot be parsed.
    """
    if level not in _PROMPTS:
        raise RewriteError(f"Invalid rewrite level: {level}")

    system_template, user_template = _PROMPTS[level]

    # Build prompt components
    style_constraint = build_style_constraint(style_profile.model_dump())
    voice_block = build_voice_block(voice_sample)
    intelligence_block = build_intelligence_block(
        intelligence_brief.model_dump() if intelligence_brief else None
    )

    system_prompt = system_template.format(style_constraint=style_constraint)
    user_prompt = user_template.format(
        resume_json=resume.model_dump_json(indent=2),
        gap_report=gap_report.model_dump_json(indent=2),
        intelligence_block=intelligence_block,
        voice_block=voice_block,
    )

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as e:
        logger.error("Claude API error during rewrite (level=%s): %s", level, e)
        raise RewriteError(
            "Failed to generate resume revisions. Please try again."
        ) from e

    raw_content = response.content[0].text.strip()

    if response.stop_reason == "max_tokens":
        logger.warning(
            "Rewrite response truncated at max_tokens (level=%s). "
            "Last 100 chars: %s", level, raw_content[-100:]
        )

    try:
        data = extract_json(raw_content)
    except json.JSONDecodeError as e:
        logger.error(
            "Failed to parse rewrite response as JSON (level=%s). "
            "Stop reason: %s. First 300 chars: %s",
            level, response.stop_reason, raw_content[:300],
        )
        raise RewriteError(
            "AI returned an invalid rewrite response. Please try again."
        ) from e

    # Level 1 returns a different structure (suggestions, not a revised resume)
    if level == "suggestions":
        # Ensure change_log exists
        if "change_log" not in data:
            data["change_log"] = [
                s.get("suggestion", "")
                for section in data.get("sections", [])
                for s in section.get("suggestions", [])
            ]
        data["rewrite_level_used"] = "suggestions"
        logger.info(
            "Rewrite (suggestions): %d sections with suggestions",
            len(data.get("sections", [])),
        )
        return data

    # Levels 2 and 3 return a full revised resume
    # Ensure rewrite metadata is present
    data["rewrite_level_used"] = level
    if "change_log" not in data:
        data["change_log"] = []

    try:
        revised = RevisedResumeSchema.model_validate(data)
    except Exception as e:
        logger.error("Rewrite data failed schema validation (level=%s): %s", level, e)
        raise RewriteError(
            "AI rewrite did not match expected format. Please try again."
        ) from e

    logger.info(
        "Rewrite (%s): %d changes logged, %d experience sections",
        level,
        len(revised.change_log),
        len(revised.experience),
    )
    return revised
