"""MCP stdio server for Agent Search SDK (mcp 1.x FastMCP and mcp 2.x MCPServer).

Runs either as a module (``python -m search_sdk.mcp_server``) or as a plain
script (``python3 search_sdk/mcp_server.py``); the launcher
``bin/agent-search-mcp`` picks an interpreter that has ``mcp`` installed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

if __package__ in (None, ""):  # script mode: make the package importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from search_sdk.client import SearchClient  # noqa: E402
from search_sdk.config import credential_provenance  # noqa: E402
from search_sdk.doctor import run_doctor  # noqa: E402
from search_sdk.settings import get_settings  # noqa: E402

def _import_server_class():
    """mcp 2.x renamed FastMCP to MCPServer; the decorator/run surface we use is identical."""
    try:
        from mcp.server.mcpserver import MCPServer  # mcp >= 2.0
        return MCPServer
    except ImportError:
        pass
    from mcp.server.fastmcp import FastMCP  # mcp 1.x
    return FastMCP


try:
    _ServerClass = _import_server_class()
except ImportError as exc:  # pragma: no cover - exercised through the launcher test
    sys.stderr.write(
        f"agent-search-mcp: the 'mcp' package is not importable by {sys.executable} ({exc}).\n"
        "Remedy: run bin/agent-search-mcp (auto-selects an interpreter with mcp), or\n"
        "  uv sync --extra mcp   (inside the project)  /  pip install 'agent-search-sdk[mcp]'\n"
    )
    sys.exit(2)

mcp = _ServerClass("agent-search")
_client: Optional[SearchClient] = None


def _get_client() -> SearchClient:
    global _client
    if _client is None:
        _client = SearchClient()
    return _client


@mcp.tool()
def agent_search(
    query: str,
    limit: int = 10,
    provider: str = "auto",
    domain: Optional[str] = None,
    mode: str = "cascade",
) -> Dict[str, Any]:
    """Web search with a fail-open cascade (Brave -> Tavily -> SerpApi -> SearXNG -> residential proxy -> DuckDuckGo).

    ``mode='fusion'`` queries every configured provider in parallel and merges with Reciprocal Rank Fusion.
    """
    return _get_client().search(query=query, limit=limit, provider=provider, domain=domain, mode=mode, on_error="skip").model_dump()


@mcp.tool()
def agent_search_doctor(live: bool = False) -> Dict[str, Any]:
    """Provider health, credential provenance (labels only), and the effective cascade."""
    return run_doctor(live=live)


@mcp.tool()
def agent_search_config() -> Dict[str, Any]:
    """Effective non-secret settings, their provenance, and where each credential was found."""
    settings = get_settings()
    return {
        "config_path": str(settings.config_path),
        "loaded": settings.config_loaded,
        "settings": settings.redacted(),
        "provenance": {k: v for k, v in settings.provenance.items() if v != "default"},
        "credentials": credential_provenance(),
        "warnings": settings.warnings,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
