"""Search providers package and the single provider registry the client and CLI derive from."""

from typing import Dict, Type

from .base import BaseSearchProvider
from .brave import BraveSearchProvider
from .tavily import TavilySearchProvider
from .serpapi import SerpApiSearchProvider
from .google import GoogleSearchProvider
from .duckduckgo import DuckDuckGoSearchProvider
from .searxng import SearxngSearchProvider
from .residential_proxy import ResidentialProxySearchProvider

# Order here is display order. ``google`` is intentionally absent: Google Custom
# Search JSON API is closed to new projects (HTTP 403) and sunsets 2027-01-01.
PROVIDER_REGISTRY: Dict[str, Type[BaseSearchProvider]] = {
    "brave": BraveSearchProvider,
    "tavily": TavilySearchProvider,
    "serpapi": SerpApiSearchProvider,
    "searxng": SearxngSearchProvider,
    "residential_proxy": ResidentialProxySearchProvider,
    "duckduckgo": DuckDuckGoSearchProvider,
}

__all__ = [
    "BaseSearchProvider",
    "BraveSearchProvider",
    "TavilySearchProvider",
    "SerpApiSearchProvider",
    "GoogleSearchProvider",
    "DuckDuckGoSearchProvider",
    "SearxngSearchProvider",
    "ResidentialProxySearchProvider",
    "PROVIDER_REGISTRY",
]
