"""LLM call to distill raw search results into an IntelligenceBrief.

Takes SearchResults from the fetcher and produces a validated
IntelligenceBrief via Claude.
"""

import json
import logging
import os
from datetime import datetime

import anthropic

from models.schemas import IntelligenceBrief
from modules.intelligence.cache import get_cached_brief, store_brief
from modules.intelligence.fetcher import SearchResults, fetch_intelligence
from modules.llm_helpers import CLAUDE_MODEL, extract_json
from prompts.intelligence import DISTILLATION_SYSTEM, DISTILLATION_USER

logger = logging.getLogger(__name__)

# Token budget for input truncation (per leg)
MAX_CONTENT_CHARS_PER_LEG = 3000


def _get_iso_week() -> str:
    """Return current ISO week string, e.g. '2026-W11'."""
    now = datetime.now()
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


def _truncate_leg(content_list: list[str], max_chars: int) -> str:
    """Join and truncate content to stay within token budget."""
    joined = "\n\n".join(content_list)
    if len(joined) > max_chars:
        joined = joined[:max_chars] + "\n[...truncated]"
    return joined if joined.strip() else "(no results)"


def distill_intelligence(
    role_category: str,
    industry: str,
    search_results: SearchResults | None = None,
) -> IntelligenceBrief | None:
    """Produce an IntelligenceBrief from web search results via Claude.

    Checks cache first. If miss, fetches (if search_results not provided),
    distills via Claude, caches the result, and returns it.

    Args:
        role_category: Target role.
        industry: Target industry.
        search_results: Pre-fetched results (if None, fetcher is called).

    Returns:
        IntelligenceBrief on success, None on total failure (graceful degradation).
    """
    week = _get_iso_week()

    # Check cache
    cached = get_cached_brief(role_category, industry, week)
    if cached is not None:
        return cached

    # Fetch if not provided
    if search_results is None:
        search_results = fetch_intelligence(role_category, industry)

    # Check if all legs are empty
    all_empty = (
        not search_results.linkedin
        and not search_results.reddit
        and not search_results.broad
    )
    if all_empty:
        logger.warning(
            "All intelligence legs returned empty for %s / %s",
            role_category,
            industry,
        )
        return None

    # Truncate for token budget
    linkedin_text = _truncate_leg(
        search_results.linkedin, MAX_CONTENT_CHARS_PER_LEG
    )
    reddit_text = _truncate_leg(
        search_results.reddit, MAX_CONTENT_CHARS_PER_LEG
    )
    broad_text = _truncate_leg(
        search_results.broad, MAX_CONTENT_CHARS_PER_LEG
    )

    user_prompt = DISTILLATION_USER.format(
        role_category=role_category,
        industry=industry,
        week=week,
        linkedin_results=linkedin_text,
        reddit_results=reddit_text,
        broad_results=broad_text,
    )

    # Call Claude
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=DISTILLATION_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as e:
        logger.error("Claude API error during distillation: %s", e)
        return None

    raw_content = response.content[0].text.strip()

    try:
        data = extract_json(raw_content)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse distillation response as JSON: %s", e)
        return None

    try:
        brief = IntelligenceBrief.model_validate(data)
    except Exception as e:
        logger.error("Distillation response failed schema validation: %s", e)
        return None

    # Cache the result
    store_brief(brief)

    logger.info(
        "Intelligence distilled: %d rewards, %d skips, %d red flags, legs: %s",
        len(brief.what_recruiters_reward),
        len(brief.what_recruiters_skip),
        len(brief.red_flags),
        brief.legs_populated,
    )
    return brief
