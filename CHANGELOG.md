# Changelog

## 1.1.1 — 2026-09-04

- Removed legacy `web-search-manager/.env` from the default credential search paths: that skill was deleted (all three of its keys were duplicates of the project `.env` and `mcp-flight-search/.env`; archive at `~/.config/agent-search-sdk/archive/`). Missing paths were already harmless; this keeps the default list free of dead routes.

## 1.1.0 — 2026-09-04

Debug pass graded against real pages, plus the configuration and test
infrastructure the fixes needed.

### Fixed
- **DuckDuckGo fallback returned ads**: the Lite page opens with sponsored
  rows on `duckduckgo.com/y.js` plus "more info" help links; URLs kept `&amp;`;
  snippets were attached by index and landed on the wrong row. Parser is now
  row-based, filters ads/help hosts (configurable), unescapes entities, and
  raises a named error on the HTTP 202 "anomaly" bot challenge so the cascade
  skips instead of returning junk. Real captured pages live in `tests/fixtures/`.
- **Brave `published_date='True'`**: boolean `family_friendly` was used as a
  date fallback. Only `page_age`/`age` strings are used now.
- **MCP entry point could not start** (`No module named 'mcp'`, relative
  imports in script mode). New `bin/agent-search-mcp` launcher; server runs
  under mcp 1.x (`FastMCP`) and 2.x (`MCPServer`); `uv.lock` committed.
- **1Password cache poisoning**: a failed resolve wrote an all-empty dict
  cached for 24 h. Empty results are no longer cached; the Cloudflare Access
  token is now among the resolved items (field labels verified against the vault).
- Fusion mode mutated provider results in place; it now copies.

### Added
- `search_sdk/settings.py`: config file (`$AGENT_SEARCH_CONFIG` or
  `~/.config/agent-search-sdk/config.json`) + env overrides with provenance;
  presets, retry policy, per-provider timeouts, SearXNG URL/language, scraper
  dir, DDG backend/blocked hosts, and all credential lookup routes are settings.
- `agent-search config show | init | path`, `--version`, `--on-error raise`.
- `search_sdk/http.py`: one transport with retry on 429/503 honouring
  `Retry-After` (capped), typed `HTTPStatusError`/`TransportError`.
- `doctor` prints credential provenance labels and the effective cascade;
  MCP tool `agent_search_config`.
- Optional `ddgs` backend for DuckDuckGo (`pip install 'agent-search-sdk[ddg]'`).
- Tests: single sandbox owner, process-level CLI and MCP tests, structural
  gates (every provider has unit + live coverage; sandbox import order; nothing
  below the main guard), honest live suite (`on_error=raise`, organic grading).
- `operations/health-checks.md`, `docs/architecture.md` filled.

### Changed
- Google Custom Search removed from the provider registry and CLI choices
  (API closed to new projects; class kept importable).
- `web-search-manager` skill superseded (banner + pointer); this SDK still
  reads its `.env`.

## 1.0.0 — 2026-09-03

Initial release: fail-open cascade over Brave, Tavily, SerpApi pool, SearXNG,
residential proxy, DuckDuckGo; RRF fusion; CLI; FastMCP server; presets.
