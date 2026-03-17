"""Gap analysis: Resume + JD + IntelligenceBrief to GapReport.

Compares structured resume against job description (if provided) and
recruiter intelligence to produce a prioritized list of gaps.
"""

import json
import logging
import os

import anthropic

from models.schemas import GapReport, IntelligenceBrief, ResumeSchema
from modules.llm_helpers import CLAUDE_MODEL, extract_json
from prompts.analysis import (
    GAP_ANALYSIS_SYSTEM,
    GAP_ANALYSIS_WITH_JD_USER,
    GAP_ANALYSIS_WITHOUT_JD_USER,
)

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Raised when gap analysis fails."""


def analyze_gaps(
    resume: ResumeSchema,
    job_posting: str | None = None,
    intelligence_brief: IntelligenceBrief | None = None,
) -> GapReport:
    """Produce a GapReport by comparing resume against JD and intelligence.

    Args:
        resume: Structured resume data.
        job_posting: Raw job description text (optional).
        intelligence_brief: Distilled recruiter intelligence (optional).

    Returns:
        Validated GapReport instance.

    Raises:
        AnalysisError: If the API call fails or response cannot be parsed.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    resume_json = resume.model_dump_json(indent=2)
    intel_json = (
        intelligence_brief.model_dump_json(indent=2)
        if intelligence_brief
        else "(no intelligence brief available)"
    )

    if job_posting:
        user_prompt = GAP_ANALYSIS_WITH_JD_USER.format(
            resume_json=resume_json,
            job_posting=job_posting,
            intelligence_brief=intel_json,
        )
    else:
        user_prompt = GAP_ANALYSIS_WITHOUT_JD_USER.format(
            resume_json=resume_json,
            intelligence_brief=intel_json,
        )

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=GAP_ANALYSIS_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as e:
        logger.error("Claude API error during gap analysis: %s", e)
        raise AnalysisError(
            "Failed to analyze resume gaps. Please try again."
        ) from e

    raw_content = response.content[0].text.strip()

    try:
        data = extract_json(raw_content)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse gap analysis response as JSON: %s", e)
        raise AnalysisError(
            "AI returned an invalid gap analysis. Please try again."
        ) from e

    try:
        report = GapReport.model_validate(data)
    except Exception as e:
        logger.error("Gap analysis data failed schema validation: %s", e)
        raise AnalysisError(
            "AI gap analysis did not match expected format. Please try again."
        ) from e

    high = sum(1 for g in report.gaps if g.severity == "high")
    med = sum(1 for g in report.gaps if g.severity == "medium")
    low = sum(1 for g in report.gaps if g.severity == "low")
    logger.info(
        "Gap analysis complete: %d gaps (high=%d, medium=%d, low=%d), jd_provided=%s",
        len(report.gaps),
        high,
        med,
        low,
        report.jd_provided,
    )
    return report
