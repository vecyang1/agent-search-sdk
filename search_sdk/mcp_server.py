"""FastMCP JSON-RPC server for Agent Search SDK."""

from __future__ import annotations

import sys
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP
from .client import SearchClient
from .doctor import run_doctor

mcp = FastMCP("agent-search")
_client = SearchClient()


@mcp.tool()
def agent_search(
    query: str,
    limit: int = 10,
    provider: str = "auto",
    domain: Optional[str] = None,
    mode: str = "cascade",
) -> Dict[str, Any]:
    """
    Search the web with fail-open multi-provider cascade across Brave, Tavily, SerpApi, Google, and DuckDuckGo.
    Supports mode='cascade' (fail-open fallback) or mode='fusion' (parallel multi-engine consensus).
    """
    resp = _client.search(
        query=query,
        limit=limit,
        provider=provider,
        domain=domain,
        mode=mode,
        on_error="skip",
    )
    return resp.model_dump()


@mcp.tool()
def agent_search_doctor(live: bool = False) -> Dict[str, Any]:
    """Audit connectivity, latency, and quota status across all search providers."""
    return run_doctor(live=live)


if __name__ == "__main__":
    mcp.run()
