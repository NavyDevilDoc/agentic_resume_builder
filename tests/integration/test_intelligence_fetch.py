"""Tests for intelligence fetch pipeline — mocked Tavily + Claude for unit, live gated behind integration mark.

Despite living in integration/, the non-marked tests here use mocks and
run as part of the default test suite. Only @pytest.mark.integration tests
make live API calls.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import IntelligenceBrief
from modules.intelligence.distiller import distill_intelligence, _truncate_leg
from modules.intelligence.fetcher import SearchResults, fetch_intelligence


# ── Fetcher tests (mocked Tavily) ──────────────────────────────────────

class TestFetcherMocked:
    @patch("modules.intelligence.fetcher.TavilyClient")
    @patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"})
    def test_returns_search_results(self, mock_tavily_cls):
        mock_client = MagicMock()
        mock_tavily_cls.return_value = mock_client
        mock_client.search.return_value = {
            "results": [
                {"content": "Recruiters love quantified impact"},
                {"content": "Use standard section headings"},
            ]
        }

        results = fetch_intelligence("AI/ML Engineer", "Defense")

        assert isinstance(results, SearchResults)
        assert len(results.linkedin) == 2
        assert len(results.reddit) == 2
        assert len(results.broad) == 2
        assert mock_client.search.call_count == 3

    @patch("modules.intelligence.fetcher.TavilyClient")
    @patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"})
    def test_handles_search_failure(self, mock_tavily_cls):
        mock_client = MagicMock()
        mock_tavily_cls.return_value = mock_client
        mock_client.search.side_effect = Exception("API down")

        results = fetch_intelligence("AI/ML Engineer", "Defense")

        assert results.linkedin == []
        assert results.reddit == []
        assert results.broad == []

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_returns_empty(self):
        # Remove TAVILY_API_KEY
        import os
        os.environ.pop("TAVILY_API_KEY", None)

        results = fetch_intelligence("AI/ML Engineer", "Defense")
        assert results.linkedin == []


# ── Truncation tests ───────────────────────────────────────────────────

class TestTruncation:
    def test_within_limit(self):
        result = _truncate_leg(["short text"], max_chars=1000)
        assert result == "short text"

    def test_exceeds_limit(self):
        long_items = ["a" * 500, "b" * 500]
        result = _truncate_leg(long_items, max_chars=600)
        assert len(result) <= 620  # 600 + "[...truncated]"
        assert result.endswith("[...truncated]")

    def test_empty_list(self):
        result = _truncate_leg([], max_chars=1000)
        assert result == "(no results)"


# ── Distiller tests (mocked Claude) ───────────────────────────────────

VALID_BRIEF_JSON = json.dumps({
    "role_category": "AI/ML Engineer",
    "industry": "Defense",
    "week": "2026-W11",
    "what_recruiters_reward": ["quantified impact"],
    "what_recruiters_skip": ["generic summaries"],
    "red_flags": ["typos"],
    "format_preferences": ["one page"],
    "current_ats_notes": ["standard headings"],
    "source_credibility_notes": "Good mix of sources",
    "legs_populated": ["linkedin", "broad"],
})


def _mock_claude_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


class TestDistillerMocked:
    @patch("modules.intelligence.distiller.get_cached_brief", return_value=None)
    @patch("modules.intelligence.distiller.store_brief")
    @patch("modules.intelligence.distiller.anthropic.Anthropic")
    def test_distill_success(self, mock_anthropic_cls, mock_store, mock_cache_get):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(
            VALID_BRIEF_JSON
        )

        search_results = SearchResults(
            linkedin=["Recruiters love metrics"],
            reddit=["Don't use Comic Sans"],
            broad=["Use action verbs"],
        )

        result = distill_intelligence(
            "AI/ML Engineer", "Defense", search_results=search_results
        )

        assert isinstance(result, IntelligenceBrief)
        assert result.role_category == "AI/ML Engineer"
        assert "quantified impact" in result.what_recruiters_reward
        mock_store.assert_called_once()

    @patch("modules.intelligence.distiller.get_cached_brief")
    def test_returns_cached(self, mock_cache_get):
        cached_brief = IntelligenceBrief(
            role_category="AI/ML Engineer",
            industry="Defense",
            week="2026-W11",
            what_recruiters_reward=["cached point"],
            legs_populated=["linkedin"],
        )
        mock_cache_get.return_value = cached_brief

        result = distill_intelligence("AI/ML Engineer", "Defense")

        assert result is not None
        assert result.what_recruiters_reward == ["cached point"]

    @patch("modules.intelligence.distiller.get_cached_brief", return_value=None)
    def test_all_empty_returns_none(self, mock_cache_get):
        search_results = SearchResults()  # all empty

        result = distill_intelligence(
            "AI/ML Engineer", "Defense", search_results=search_results
        )

        assert result is None

    @patch("modules.intelligence.distiller.get_cached_brief", return_value=None)
    @patch("modules.intelligence.distiller.anthropic.Anthropic")
    def test_api_error_returns_none(self, mock_anthropic_cls, mock_cache_get):
        import anthropic

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="rate limited",
            request=MagicMock(),
            body=None,
        )

        search_results = SearchResults(linkedin=["some content"])
        result = distill_intelligence(
            "AI/ML Engineer", "Defense", search_results=search_results
        )

        assert result is None

    @patch("modules.intelligence.distiller.get_cached_brief", return_value=None)
    @patch("modules.intelligence.distiller.store_brief")
    @patch("modules.intelligence.distiller.anthropic.Anthropic")
    def test_invalid_json_returns_none(self, mock_anthropic_cls, mock_store, mock_cache_get):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(
            "Not valid JSON at all"
        )

        search_results = SearchResults(linkedin=["content"])
        result = distill_intelligence(
            "AI/ML Engineer", "Defense", search_results=search_results
        )

        assert result is None
        mock_store.assert_not_called()
