"""Normalized data models for Agent Search SDK."""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """A normalized single search result from any search engine provider."""
    title: str
    url: str
    snippet: str = ""
    source: str = Field(description="Search provider name: brave, tavily, serpapi, google, duckduckgo")
    score: Optional[float] = None
    published_date: Optional[str] = None
    raw: Optional[Dict[str, Any]] = Field(default=None, description="Original provider payload for debugging")


class SearchResponse(BaseModel):
    """Complete search response with metadata and skipped providers."""
    query: str
    provider: str = Field(description="The provider that fulfilled this query")
    results: List[SearchResult] = Field(default_factory=list)
    total_results: int = 0
    execution_time_ms: float = 0.0
    skipped_providers: List[str] = Field(
        default_factory=list,
        description="Providers attempted but skipped due to error, timeout, or quota exhaustion"
    )
    success: bool = True
    error: Optional[str] = None

    def __iter__(self):
        return iter(self.results)

    def __len__(self):
        return len(self.results)

    def __getitem__(self, index):
        return self.results[index]


class ProviderHealth(BaseModel):
    """Health diagnostic status for an individual search provider."""
    provider: str
    status: str = Field(description="healthy, degraded, exhausted, unconfigured, error")
    configured: bool
    latency_ms: Optional[float] = None
    quota_note: Optional[str] = None
    error: Optional[str] = None
