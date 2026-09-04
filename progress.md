# Progress

Use this file for dated execution evidence, verification outputs, blockers, and
meaningful state changes. Do not turn `VAULT.md` into a session diary.

## 2026-09-03 20:17

- Initialized or prepared the V.A.U.L.T. project knowledge structure.
- Evidence paths: `VAULT.md`, `AGENTS.md`, `task_plan.md`, `handoff.md`,
  `FILE_MAP_INDEX.md`, `vault/README.md`.
- Skills used: `init-vault-method` for scaffold creation. Add every
  task-specific skill used in later sessions here.
- Canonical skill-call log: Every meaningful work block should leave a
  `Skills used:` line in this file. Keep skill-call records in this file only;
  link to `vault/sessions/YYYY-MM-DD-[topic].md` for detailed evidence when
  needed instead of duplicating the skill list there.

## 2026-09-03 20:25 — Initial Release v1.0.0

- Built `search_sdk` with multi-provider fail-open cascade:
  1. Brave Search (1,000 queries/month free, privacy-focused, ~730ms latency)
  2. Tavily AI Search (1,000 queries/month free, optimized for LLM contexts, ~810ms latency)
  3. SerpApi Google Search with resilient multi-key pool rotation (497+ free queries across accounts)
  4. Google Custom Search JSON API provider (ready for GCP project toggle)
  5. DuckDuckGo Direct (zero-key free emergency fallback)
- Implemented `SearchClient` enforcing 'use or skip' semantics: if any provider errors or hits rate limit, it skips to the next tier without throwing unhandled exceptions to the calling agent.
- Built CLI `bin/agent-search` with query execution, `--domain` filters, `--json` serialization, and `doctor` live audit suite.
- Built FastMCP JSON-RPC server (`search_sdk/mcp_server.py`) exposing `agent_search` and `agent_search_doctor`.
- Built comprehensive test suites:
  - `run_tests.py`: 14/14 unit & cascade tests passing in 0.01s.
  - `tests/test_live.py`: 4/4 real live network tests passing in 8.2s across Brave, Tavily, and DuckDuckGo.
- Created global skill `agent-search-sdk` and logged in `~/.gemini/antigravity/skills/installation_log.md`.

## 2026-09-03 20:46 — GitHub & Notion Product[OS] Release

- Added Reciprocal Rank Fusion (RRF) search mode (`--mode fusion`) combining parallel multi-engine results with URL canonicalization.
- Expanded unit test suite to 15/15 tests passing.
- Initialized Git repository and published public open-source repository to GitHub: `https://github.com/vecyang1/agent-search-sdk` (AGPL-3.0).
- Safely pushed project to Notion `Product[OS]` (`251e1b43-2393-802e-9d47-f79037c1794d`) via `notion-mcp-connector`:
  - Created page `Agent Search SDK (agent-search-sdk)` (ID: `3d0e1b43-2393-81b1-bcb0-c52943895b66`).
  - Set properties: `Pipeline = Shipped`, `Product Role = Standalone`, `Tag = Product, Skill`, `Rating = ⭐️⭐️⭐️⭐️⭐️`, `Done = 2026-09-03`.
  - Set `Note`: `https://github.com/vecyang1/agent-search-sdk | Fail-open multi-provider Search SDK and CLI for autonomous AI agents across Brave, Tavily, SerpApi, Google, and DuckDuckGo (AGPL-3.0)`.
  - Rendered full enhanced Markdown documentation body with links, architecture breakdown, CLI examples, MCP server configuration, and live test proofs.
- Skills used: `notion-mcp-connector`, `init-vault-method`.


## 2026-09-04 15:10 — Debug pass: real-page comparison (diagnosis)

Suite `run_tests.py` 23/23 green and `doctor --live` 6/6 healthy, yet querying
each provider for `Cat Ba Island Vietnam` and reading the fields found:

- `duckduckgo` returns **ads first**: 4 of 14 `result-link` anchors on the live
  Lite page are `duckduckgo.com/y.js?ad_domain=…` + "more info" ads-help links;
  URLs keep `&amp;`; snippets (12) are index-misaligned with links (14). A
  second request got **HTTP 202 anomaly challenge** with 0 links. Live test
  passed on "≥1 result".
- `brave` emits `published_date='True'` (falls back to boolean `family_friendly`).
- Documented MCP entry `python3 search_sdk/mcp_server.py` exits 1:
  `No module named 'mcp'` on system Python 3.14 (present in python3.10 and
  web-search-manager/.venv); relative import also breaks script mode.
- `config.py` writes an all-`None` dict to the 24h credential cache when the
  1Password resolve fails (cache poisoning); CF Access token is not among the
  resolved items despite README claim.
- Live tests accept fallback providers (`brave` test passes on tavily/ddg), a
  `HTTPError 429` leaked through a green run (Brave free tier is 1 QPS; no retry).
- Hardcoded: 1Password item titles, cross-skill `.env` paths, SearXNG URL,
  scraper scripts dir, CLI `--provider/--preset` choices.
- `web-search-manager` (576 lines, own MCP) is a parallel wheel with no pointer
  to this SDK; SDK MCP is not in `mcp_registry.md`.
- Packaging OK: `uv build` wheel installs in a clean py3.14 venv and
  `agent-search --help` runs from outside the tree.

Fixtures captured from real bytes: scratchpad `ddg_lite_catba_200.html`
(28,593 B, 14 links) and `ddg_lite_catba.html` (202 anomaly, 14,210 B) → to be
copied into `tests/fixtures/`.

Plan: settings layer (config file + env precedence) → shared HTTP helper with
Retry-After → provider fixes (TDD from fixtures) → honest live tests + process
CLI test + coverage gate → MCP launcher → docs/skill/registry consolidation →
bump 1.1.0 → push. Skills used: `graphify`, `wheel-check` (ddgs 2.9k★ MIT as
optional DDG backend; extend not fork).

## 2026-09-04 15:45 — v1.1.0 shipped: fixes, settings layer, honest tests, MCP launcher

Evidence (all run sequentially this session; Brave is 1 req/s):

- Hermetic: `python3 run_tests.py` → `files=15 tests=88 failures=0 errors=0 skipped=0 real_cache_untouched=True`
  (discovery-based runner; single sandbox owner `tests/_sandbox.py`; gates graded
  6 providers ×2, 3 CLI subcommands, 15 hermetic modules, 16 test files).
- Live: `python3 tests/test_live.py` → 9/9 OK, every provider asked directly with
  `on_error=raise` and graded organic (no ad hosts, no `&amp;`, no bool dates);
  DuckDuckGo answered organically this run (10 rows on the page, 4 ads filtered).
- `agent-search doctor --live` → HEALTHY 6/6 (brave 750 ms, tavily 942, serpapi 794,
  searxng 4035, residential_proxy 4660, duckduckgo 1190) + provenance labels
  (brave/tavily/serpapi from project `.env`; searxng CF from token file).
- Real PATH entry `~/.local/bin/agent-search "Cat Ba Island Vietnam" --limit 3` → brave, 3 rows, 743 ms.
- MCP: `bin/agent-search-mcp` → `.venv/bin/python` (3.13, mcp 2.1.1); `initialize` →
  `tools/list` (3 tools) → `tools/call agent_search {"query":"Hoi An ancient town"}` →
  brave, 2 rows, 0.8 s. Test client must keep stdin open (server exits on EOF).
- `ddgs` backend (optional extra) exercised once in `.venv`: 3 organic rows, 10.4 s →
  `auto` now = Lite first, `ddgs` only on the 202 challenge.
- Packaging: `uv build --wheel` → installs into a clean py3.14 venv; `agent-search --help` from outside the tree.
- 1Password field labels verified read-only against the vault: API items use `credential`; CF item uses `client_id` + `credential`.

Write-backs: skill `agent-search-sdk` (routing table + `references/{config,mcp,troubleshooting}.md`),
`web-search-manager` superseded banner, `mcp_registry.md` row, `installation_log.md` row
(committed in `~/.gemini/antigravity` as `65d8905f`), project memory `project_agent_search_sdk.md`.
Not applied (user decision): global MCP registration; retiring the `web-search-manager` folder.

Skills used: `graphify` (map built, 299 nodes), `wheel-check` (ddgs 2.9k★ MIT as optional backend; extend not fork), `1password` (unattended bridge, labels-only read), `starting-with-readiness`, `finishing-with-writeback`.

## 2026-09-04 18:50 — Retired `web-search-manager` (merge already complete → delete)

Pre-checks: no MCP registration in `~/.claude.json` (only `skillUsage` telemetry),
Antigravity, Codex, Claude Desktop, or any project `.mcp.json`; no running process;
its 3 `.env` values hashed equal to keys already in project `.env` / `mcp-flight-search/.env`;
`config/keys.json` = dead Google CSE pool, archived 08-26 at `~/.config/search/google_cse_pool.json`.
Safety: folder archived with `.env` (no `.venv`) to `~/.config/agent-search-sdk/archive/web-search-manager-2026-09-04.tar.gz` (0600);
13 source files remain in `~/.gemini/antigravity` git history.
Repointed 6 references (skill-orchestrator `skill_relationships.json` + `skill_domain_map.json` entries renamed to
`agent-search-sdk`; `cross-border-ai-strategist`, `claude-cli-guide` ×2, `email-management` refs).
SDK 1.1.1: default `credentials.env_files` no longer lists the deleted path. Read-back after deletion recorded below.

Read-back after deletion (2026-09-04 19:05): `~/.gemini/antigravity/skills/web-search-manager` and the
`~/.claude/skills/web-search-manager` symlink are gone (re-verified after 2 s; no launchd sync recreates them);
`agent-search doctor --json` from `/` → healthy, 6/6 configured, SerpApi pool still 3 keys, brave/tavily via
project `.env`; live-reference scan over MCP configs, `mcp_registry.md`, every `SKILL.md` and `references/*.md`:
1 live route(s) left, 4 historical mentions kept; `~/.claude.json` `mcpServers` has no entry
(the one match is `skillUsage` telemetry). Skills repo commits `5b65fa29`, `01e40038`; SDK 1.1.1 `9955bea` pushed.

