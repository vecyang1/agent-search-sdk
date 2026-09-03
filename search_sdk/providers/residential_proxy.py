"""Residential Proxy Search Provider using ultra-low-cost-scraper transport.

The 'Heavy Shield' for bypassing datacenter IP bans, rate limits, and CAPTCHAs
via wholesale DataImpulse residential proxy pools with TLS chrome120 browser impersonation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

from .base import BaseSearchProvider
from ..models import SearchResult

# Try importing search_adapter from canonical ultra-low-cost-scraper location
_SCRAPER_SCRIPTS = Path.home() / ".agents" / "skills" / "ultra-low-cost-scraper" / "scripts"
if _SCRAPER_SCRIPTS.exists() and str(_SCRAPER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRAPER_SCRIPTS))


class ResidentialProxySearchProvider(BaseSearchProvider):
    """Residential Proxy Search Provider backed by ultra-low-cost-scraper."""

    def __init__(
        self,
        geo: str = "us",
        timeout: int = 15,
    ):
        self.geo = geo
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "residential_proxy"

    def is_configured(self) -> bool:
        # Check if ultra-low-cost-scraper scripts exist
        return (_SCRAPER_SCRIPTS / "search_adapter.py").exists()

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        try:
            import search_adapter
        except ImportError as e:
            raise RuntimeError(f"ultra-low-cost-scraper not available: {e}") from e

        geo = kwargs.get("geo", self.geo)
        res = search_adapter.search(
            query=query,
            count=limit,
            engine="proxy",
            geo=geo,
            timeout=self.timeout,
        )

        raw_items = res.get("results", [])
        if not raw_items:
            err = res.get("error") or "No results returned via residential proxy"
            raise RuntimeError(f"Residential proxy search failed: {err}")

        results: List[SearchResult] = []
        for item in raw_items[:limit]:
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source=self.name,
                    raw=item,
                )
            )

        return results
