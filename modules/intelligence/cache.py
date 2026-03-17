"""JSON cache keyed by (role_category, industry, iso_week).

Caches only distilled IntelligenceBriefs, never raw search results.
TTL: 7 days. Designed so the caller interface won't change when
upgrading to a shared cache (Redis) in v2.
"""

import hashlib
import json
import logging
import time
from pathlib import Path

from models.schemas import IntelligenceBrief

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "intelligence_cache"
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def _cache_key(role_category: str, industry: str, week: str) -> str:
    """Generate a filesystem-safe cache key."""
    raw = f"{role_category.lower().strip()}:{industry.lower().strip()}:{week}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_path(role_category: str, industry: str, week: str) -> Path:
    return CACHE_DIR / f"{_cache_key(role_category, industry, week)}.json"


def get_cached_brief(
    role_category: str, industry: str, week: str
) -> IntelligenceBrief | None:
    """Retrieve a cached IntelligenceBrief if it exists and is not expired.

    Args:
        role_category: Target role.
        industry: Target industry.
        week: ISO week string (e.g., "2026-W11").

    Returns:
        IntelligenceBrief if cache hit and not expired, else None.
    """
    path = _cache_path(role_category, industry, week)

    if not path.exists():
        logger.debug("Cache miss: %s / %s / %s", role_category, industry, week)
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Corrupt cache file %s: %s", path.name, e)
        return None

    # Check TTL
    cached_at = data.get("_cached_at", 0)
    if time.time() - cached_at > CACHE_TTL_SECONDS:
        logger.info("Cache expired: %s / %s / %s", role_category, industry, week)
        path.unlink(missing_ok=True)
        return None

    try:
        brief = IntelligenceBrief.model_validate(data["brief"])
    except Exception as e:
        logger.warning("Cache data failed validation: %s", e)
        return None

    logger.info("Cache hit: %s / %s / %s", role_category, industry, week)
    return brief


def store_brief(brief: IntelligenceBrief) -> None:
    """Write an IntelligenceBrief to the cache.

    Args:
        brief: The distilled brief to cache.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    path = _cache_path(brief.role_category, brief.industry, brief.week)
    payload = {
        "_cached_at": time.time(),
        "brief": brief.model_dump(),
    }

    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info(
            "Cached brief: %s / %s / %s",
            brief.role_category,
            brief.industry,
            brief.week,
        )
    except OSError as e:
        logger.error("Failed to write cache: %s", e)


def clear_cache() -> int:
    """Remove all cached files. Returns number of files removed."""
    if not CACHE_DIR.exists():
        return 0
    removed = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        removed += 1
    logger.info("Cleared %d cache files", removed)
    return removed
