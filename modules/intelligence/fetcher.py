"""Web search queries and source filtering for recruiter intelligence.

Implements the tripod sourcing model:
  - LinkedIn: recruiter/TA posts and articles (advanced depth)
  - Reddit: r/resumes, r/recruitinghell, r/cscareerquestions
  - Broad: career coaching, industry blogs, niche job boards

Uses Tavily API for web search.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime

from tavily import TavilyClient

logger = logging.getLogger(__name__)


@dataclass
class SearchResults:
    """Raw search results from the tripod sourcing model."""
    linkedin: list[str] = field(default_factory=list)
    reddit: list[str] = field(default_factory=list)
    broad: list[str] = field(default_factory=list)


def _extract_content(results: dict) -> list[str]:
    """Extract content strings from a Tavily search response."""
    if not results or "results" not in results:
        return []
    return [
        r.get("content", "")
        for r in results["results"]
        if r.get("content")
    ]


def _search_tavily(
    client: TavilyClient,
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
) -> dict:
    """Execute a single Tavily search with error handling."""
    try:
        return client.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
        )
    except Exception as e:
        logger.warning("Tavily search failed for query '%s': %s", query, e)
        return {}


def _merge_results(*result_lists: list[str]) -> list[str]:
    """Merge multiple result lists, deduplicating by content."""
    seen = set()
    merged = []
    for results in result_lists:
        for item in results:
            # Deduplicate by first 100 chars to catch near-duplicates
            key = item[:100].lower().strip()
            if key not in seen:
                seen.add(key)
                merged.append(item)
    return merged


def fetch_intelligence(role_category: str, industry: str) -> SearchResults:
    """Execute tripod sourcing queries via Tavily.

    Uses refined, targeted queries with fallback variants per leg.
    LinkedIn leg uses advanced search depth for higher signal quality.

    Args:
        role_category: Target role (e.g., "AI/ML Engineer").
        industry: Target industry (e.g., "Defense").

    Returns:
        SearchResults with content from each leg. Empty lists for
        legs that failed or returned no results.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.error("TAVILY_API_KEY not set — skipping intelligence fetch")
        return SearchResults()

    client = TavilyClient(api_key=api_key)
    year = datetime.now().year
    results = SearchResults()

    # ── Leg 1: LinkedIn — primary authority (advanced depth) ───────────
    # Primary: first-person recruiter perspectives
    linkedin_primary = (
        f'"hiring manager" OR "recruiter" "{role_category}" resume '
        f'"what I look for" OR "what stands out" OR "common mistakes" '
        f"site:linkedin.com"
    )
    # Fallback: broader recruiter tips
    linkedin_fallback = (
        f'"{role_category}" resume {year} recruiter tips '
        f'"talent acquisition" OR "hiring" site:linkedin.com'
    )
    logger.info("LinkedIn primary query: %s", linkedin_primary)
    primary_raw = _search_tavily(client, linkedin_primary, search_depth="advanced")
    primary_results = _extract_content(primary_raw)

    if len(primary_results) < 2:
        logger.info("LinkedIn primary returned < 2 results, running fallback")
        logger.info("LinkedIn fallback query: %s", linkedin_fallback)
        fallback_raw = _search_tavily(client, linkedin_fallback, search_depth="advanced")
        fallback_results = _extract_content(fallback_raw)
        results.linkedin = _merge_results(primary_results, fallback_results)
    else:
        results.linkedin = primary_results

    # ── Leg 2: Reddit — failure signals and red flags ──────────────────
    # Primary: rejection signals and negative patterns
    reddit_primary = (
        f'"{role_category}" resume rejected OR "instant no" OR "red flag" '
        f"site:reddit.com (r/resumes OR r/recruitinghell OR r/cscareerquestions)"
    )
    # Fallback: general resume feedback
    reddit_fallback = (
        f'"{role_category}" resume feedback review '
        f"site:reddit.com r/resumes"
    )
    logger.info("Reddit primary query: %s", reddit_primary)
    reddit_raw = _search_tavily(client, reddit_primary)
    reddit_results = _extract_content(reddit_raw)

    if len(reddit_results) < 2:
        logger.info("Reddit primary returned < 2 results, running fallback")
        logger.info("Reddit fallback query: %s", reddit_fallback)
        fallback_raw = _search_tavily(client, reddit_fallback)
        fallback_results = _extract_content(fallback_raw)
        results.reddit = _merge_results(reddit_results, fallback_results)
    else:
        results.reddit = reddit_results

    # ── Leg 3: Broad — career coaching, blogs, niche boards ────────────
    broad_primary = (
        f'"{role_category}" "{industry}" resume advice {year} '
        f"-site:linkedin.com -site:reddit.com"
    )
    broad_fallback = (
        f'"{role_category}" resume tips "hiring manager perspective" {year} '
        f"-site:linkedin.com -site:reddit.com"
    )
    logger.info("Broad primary query: %s", broad_primary)
    broad_raw = _search_tavily(client, broad_primary)
    broad_results = _extract_content(broad_raw)

    if len(broad_results) < 2:
        logger.info("Broad primary returned < 2 results, running fallback")
        logger.info("Broad fallback query: %s", broad_fallback)
        fallback_raw = _search_tavily(client, broad_fallback)
        fallback_results = _extract_content(fallback_raw)
        results.broad = _merge_results(broad_results, fallback_results)
    else:
        results.broad = broad_results

    logger.info(
        "Fetch complete — LinkedIn: %d, Reddit: %d, Broad: %d results",
        len(results.linkedin),
        len(results.reddit),
        len(results.broad),
    )
    return results
