"""Integration tests for M2: intelligence fetch + distillation with live APIs.

Only run with: pytest -m integration
Uses real Tavily + Claude API calls. Be mindful of Tavily credit usage.
"""

import pytest

from models.schemas import IntelligenceBrief
from modules.intelligence.cache import clear_cache
from modules.intelligence.distiller import distill_intelligence
from modules.intelligence.fetcher import SearchResults, fetch_intelligence

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def clean_cache_for_live():
    """Ensure no cached data interferes with live tests."""
    clear_cache()
    yield
    clear_cache()


class TestFetcherLive:
    def test_live_tavily_search(self):
        """Verify Tavily returns actual results for our tripod queries."""
        results = fetch_intelligence("AI/ML Engineer", "Defense")

        assert isinstance(results, SearchResults)
        # At least one leg should have content
        total = len(results.linkedin) + len(results.reddit) + len(results.broad)
        assert total > 0, "All three search legs returned empty — check Tavily API key"


class TestDistillerLive:
    def test_live_full_pipeline(self):
        """Full fetch -> distill -> validate pipeline."""
        brief = distill_intelligence("AI/ML Engineer", "Defense")

        # May return None if APIs are having issues, but when it works:
        if brief is None:
            pytest.skip("Intelligence fetch returned None — API may be down")

        assert isinstance(brief, IntelligenceBrief)
        assert brief.role_category == "AI/ML Engineer"
        assert brief.industry == "Defense"
        assert len(brief.legs_populated) > 0
        assert len(brief.what_recruiters_reward) > 0 or len(brief.what_recruiters_skip) > 0

    def test_live_caches_result(self):
        """Verify that a successful distillation gets cached."""
        brief = distill_intelligence("AI/ML Engineer", "Defense")

        if brief is None:
            pytest.skip("Intelligence fetch returned None")

        # Second call should hit cache (no API call)
        cached = distill_intelligence("AI/ML Engineer", "Defense")

        assert cached is not None
        assert cached.role_category == brief.role_category
        assert cached.week == brief.week
