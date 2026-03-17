"""Tests for intelligence cache — write, read, TTL expiry, key collision."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from models.schemas import IntelligenceBrief
from modules.intelligence.cache import (
    CACHE_DIR,
    clear_cache,
    get_cached_brief,
    store_brief,
    _cache_path,
)


@pytest.fixture
def sample_brief() -> IntelligenceBrief:
    return IntelligenceBrief(
        role_category="AI/ML Engineer",
        industry="Defense",
        week="2026-W11",
        what_recruiters_reward=["quantified impact", "clearance mentioned early"],
        what_recruiters_skip=["generic objective statements"],
        red_flags=["typos in technical terms"],
        format_preferences=["one page for < 10 years experience"],
        current_ats_notes=["use standard section headings"],
        source_credibility_notes="Mix of verified LinkedIn recruiters and Reddit anecdotes",
        legs_populated=["linkedin", "reddit"],
    )


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure clean cache state before and after each test."""
    clear_cache()
    yield
    clear_cache()


class TestCacheWriteRead:
    def test_store_and_retrieve(self, sample_brief):
        store_brief(sample_brief)
        result = get_cached_brief("AI/ML Engineer", "Defense", "2026-W11")

        assert result is not None
        assert result.role_category == "AI/ML Engineer"
        assert result.what_recruiters_reward == sample_brief.what_recruiters_reward
        assert result.legs_populated == ["linkedin", "reddit"]

    def test_cache_miss_returns_none(self):
        result = get_cached_brief("Nonexistent Role", "Nonexistent Industry", "2026-W99")
        assert result is None

    def test_key_is_case_insensitive(self, sample_brief):
        store_brief(sample_brief)
        # Retrieve with different casing
        result = get_cached_brief("ai/ml engineer", "defense", "2026-W11")
        assert result is not None
        assert result.role_category == "AI/ML Engineer"

    def test_different_roles_dont_collide(self, sample_brief):
        store_brief(sample_brief)

        other_brief = IntelligenceBrief(
            role_category="Data Scientist",
            industry="Defense",
            week="2026-W11",
            what_recruiters_reward=["statistics expertise"],
            legs_populated=["broad"],
        )
        store_brief(other_brief)

        result_ml = get_cached_brief("AI/ML Engineer", "Defense", "2026-W11")
        result_ds = get_cached_brief("Data Scientist", "Defense", "2026-W11")

        assert result_ml is not None
        assert result_ds is not None
        assert result_ml.role_category == "AI/ML Engineer"
        assert result_ds.role_category == "Data Scientist"

    def test_different_weeks_dont_collide(self, sample_brief):
        store_brief(sample_brief)

        other_brief = sample_brief.model_copy(update={"week": "2026-W12"})
        store_brief(other_brief)

        result_w11 = get_cached_brief("AI/ML Engineer", "Defense", "2026-W11")
        result_w12 = get_cached_brief("AI/ML Engineer", "Defense", "2026-W12")

        assert result_w11 is not None
        assert result_w12 is not None
        assert result_w11.week == "2026-W11"
        assert result_w12.week == "2026-W12"


class TestCacheTTL:
    def test_expired_cache_returns_none(self, sample_brief):
        store_brief(sample_brief)

        # Manually backdate the _cached_at timestamp
        path = _cache_path("AI/ML Engineer", "Defense", "2026-W11")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_cached_at"] = time.time() - (8 * 24 * 60 * 60)  # 8 days ago
        path.write_text(json.dumps(data), encoding="utf-8")

        result = get_cached_brief("AI/ML Engineer", "Defense", "2026-W11")
        assert result is None
        # File should be cleaned up
        assert not path.exists()

    def test_fresh_cache_returns_brief(self, sample_brief):
        store_brief(sample_brief)
        # Immediately retrieve — well within TTL
        result = get_cached_brief("AI/ML Engineer", "Defense", "2026-W11")
        assert result is not None


class TestCacheEdgeCases:
    def test_corrupt_json_returns_none(self, sample_brief):
        store_brief(sample_brief)
        path = _cache_path("AI/ML Engineer", "Defense", "2026-W11")
        path.write_text("this is not json", encoding="utf-8")

        result = get_cached_brief("AI/ML Engineer", "Defense", "2026-W11")
        assert result is None

    def test_clear_cache(self, sample_brief):
        store_brief(sample_brief)
        removed = clear_cache()
        assert removed >= 1

        result = get_cached_brief("AI/ML Engineer", "Defense", "2026-W11")
        assert result is None

    def test_clear_empty_cache(self):
        removed = clear_cache()
        assert removed == 0
