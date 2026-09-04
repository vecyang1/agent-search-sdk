# Decisions

> Scope: project-local — this file governs only this project root. Cross-project truth lives in the 2nd Brain vault: /Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain (contract: 00 - System/contracts/project-link-bridge.md).

Use this file for durable choices, supersession, reversals, and rationale.
Keep execution proof in `progress.md` or `vault/sessions/`.

| ID | Date | Decision | Status | Rationale | Evidence | Supersedes |
| --- | --- | --- | --- | --- | --- | --- |
| D-001 | 2026-09-03 | Use V.A.U.L.T. owner-doc structure for project continuity | accepted | Future agents need one owner per truth type | `VAULT.md`, `FILE_MAP_INDEX.md` | - |
| D-002 | 2026-09-03 | Fail-open multi-provider cascade with 'use or skip' semantics | accepted | Autonomous AI agents must never crash on search quota exhaustion or 429/403/timeout | `search_sdk/client.py`, `tests/test_cascade.py` | - |
| D-003 | 2026-09-04 | Settings layer (`search_sdk/settings.py`) owns every tunable and every credential *route*; precedence args > env > config file > defaults; file ignored unless it declares an owned key | accepted | "不要硬编码": presets, timeouts, SearXNG URL, scraper dir, 1Password item titles were literals; foreign `config.json` must not shadow ours | `tests/test_settings.py`, `agent-search config show` | - |
| D-004 | 2026-09-04 | One shared transport (`search_sdk/http.py`) with retry on 429/503 honouring `Retry-After` (capped); providers never call `urllib` directly | accepted | Brave free tier is 1 req/s; five providers duplicated urllib boilerplate and mapped errors differently | `tests/test_http.py` | - |
| D-005 | 2026-09-04 | DuckDuckGo parser is row-based, graded against captured real pages; ads/help hosts filtered; HTTP 202 anomaly raises a named error; optional `ddgs` backend (extend, not fork) | accepted | Real page: ads first on `duckduckgo.com`, `&amp;` in URLs, snippets misaligned by index; second request was a 202 challenge | `tests/fixtures/ddg_lite_*.html`, `tests/test_duckduckgo.py` | - |
| D-006 | 2026-09-04 | Google Custom Search removed from `PROVIDER_REGISTRY` and CLI choices; class kept importable | accepted | API closed to new projects (403), sunset 2027-01-01; a choice that always fails misleads | `tests/test_cli_process.py::test_query_rejects_unknown_provider_choice` | D-002 (provider list) |
| D-007 | 2026-09-04 | `web-search-manager` skill is superseded by this SDK; kept only as a credential source (`.env`) until no client points at its `src/server.py` | accepted | Two wheels for one job; SDK is the superset with SearXNG/proxy/DDG/presets/doctor | banner in `~/.gemini/antigravity/skills/web-search-manager/SKILL.md` | - |
| D-008 | 2026-09-04 | Live tests ask each provider directly with `on_error="raise"` and grade results for being organic; hermetic suite runs under one sandbox owner (`tests/_sandbox.py`) and asserts the real credential cache is untouched | accepted | The old Brave live test passed on a 429 because the cascade rescued it; DDG passed while returning ads | `tests/test_live.py`, `run_tests.py` summary line | - |
| D-009 | 2026-09-04 | MCP served via `bin/agent-search-mcp` launcher (interpreter with `mcp`: `$AGENT_SEARCH_PYTHON` → `.venv` → self → `uv run`); server supports mcp 1.x `FastMCP` and 2.x `MCPServer`; `uv.lock` committed | accepted | Documented entry failed with `No module named 'mcp'`; `uv sync` installed mcp 2.x which renamed the class | `tests/test_mcp_process.py`, `bin/agent-search-mcp --which` | - |
