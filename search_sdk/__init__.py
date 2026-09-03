"""Agent Search SDK - Ultra-resilient, fail-open search for autonomous AI agents."""

from .models import SearchResult, SearchResponse, ProviderHealth
from .client import SearchClient, canonicalize_url

__version__ = "1.0.0"

_DEFAULT_CLIENT = None


def get_client() -> SearchClient:
    """Get or initialize singleton default search client."""
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = SearchClient()
    return _DEFAULT_CLIENT


def search(
    query: str,
    limit: int = 10,
    provider: str = "auto",
    domain: str = None,
    mode: str = "cascade",
    on_error: str = "skip",
    **kwargs,
) -> SearchResponse:
    """
    Execute search query with automatic fail-open provider cascade or multi-engine fusion.

    Args:
        query: Search query string.
        limit: Max results (default 10).
        provider: 'auto' (Brave -> Tavily -> SerpApi -> Google -> DDG) or specific provider.
        domain: Optional domain filter (e.g. 'tripadvisor.com').
        mode: 'cascade' (sequential fail-open fallback) or 'fusion' (parallel multi-engine consensus).
        on_error: 'skip' (never crashes caller) or 'raise'.
    """
    return get_client().search(
        query=query,
        limit=limit,
        provider=provider,
        domain=domain,
        mode=mode,
        on_error=on_error,
        **kwargs,
    )


def quick_search(
    query: str,
    limit: int = 5,
    domain: str = None,
    **kwargs,
) -> list[SearchResult]:
    """Convenience shortcut returning list of SearchResults directly."""
    return get_client().quick_search(query=query, limit=limit, domain=domain, **kwargs)


__all__ = [
    "SearchClient",
    "SearchResult",
    "SearchResponse",
    "ProviderHealth",
    "canonicalize_url",
    "search",
    "quick_search",
    "get_client",
]
