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

