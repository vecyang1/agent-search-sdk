"""Abstract base class for search engine providers."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..models import SearchResult, ProviderHealth


class BaseSearchProvider(ABC):
    """Abstract contract for search providers in the cascade."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier string (e.g. brave, tavily, serpapi, google, duckduckgo)."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if required credentials or network access are available."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        """Execute search and return normalized results list."""
        pass

    def health_check(self) -> ProviderHealth:
        """Perform lightweight diagnostic probe."""
        if not self.is_configured():
            return ProviderHealth(
                provider=self.name,
                status="unconfigured",
                configured=False,
                quota_note="Credentials missing",
            )

        start = time.perf_counter()
        try:
            results = self.search("test", limit=1)
            duration_ms = (time.perf_counter() - start) * 1000
            return ProviderHealth(
                provider=self.name,
                status="healthy",
                configured=True,
                latency_ms=round(duration_ms, 1),
                quota_note=f"Probe returned {len(results)} item(s)",
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            err_str = str(e)
            status = "exhausted" if any(term in err_str.lower() for term in ["quota", "rate limit", "429", "run out"]) else "error"
            return ProviderHealth(
                provider=self.name,
                status=status,
                configured=True,
                latency_ms=round(duration_ms, 1),
                error=err_str,
            )
