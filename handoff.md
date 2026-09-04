# Handoff

| Field | Value |
| --- | --- |
| Subject | Agent Search SDK v1.1.0 — real-page debug pass, settings layer, honest test suite, MCP launcher |
| Last Updated | 2026-09-04 15:40 Asia/Bangkok |
| Updated By | Claude (Claude Code) |
| Requested By | Vec |
| Next Actor | Any autonomous agent |
| Next Required Action | None required. Optional: register MCP globally (`~/.gemini/antigravity/skills/agent-search-sdk/references/mcp.md`); retire `web-search-manager` once nothing points at its `src/server.py`. |
| Current Blocker | None. DuckDuckGo may answer HTTP 202 (external bot check); the provider raises a named error and the cascade skips. |
| Evidence | `python3 run_tests.py` → 15 files / 86 tests / 0 fail / 0 skip / real cache untouched; `python3 tests/test_live.py` → 9/9; `agent-search doctor --live` → 6/6 HEALTHY; MCP `tools/call agent_search` → brave, 2 rows, 0.8 s (all 2026-09-04) |

## Resume Notes

- Entry points: `agent-search "<q>"` (PATH symlink → `bin/agent-search`), `from search_sdk import search`, `bin/agent-search-mcp`.
- Config: `agent-search config init|show|path`; precedence args > env > `~/.config/agent-search-sdk/config.json` > defaults (`search_sdk/settings.py`).
- Where credentials come from: `agent-search doctor` prints labels (`env:` / `file:` / `token_file:` / `1password:` / `none`).
- Tests: `run_tests.py` discovers `tests/test_*.py` except `test_live*`; `tests/_sandbox.py` is the single hermetic owner; `tests/test_gate_coverage.py` refuses a provider without a unit + live test.
- Checks and what they prove: `operations/health-checks.md`. Brave is 1 req/s — run live checks one at a time.
- Skill for other agents: `~/.gemini/antigravity/skills/agent-search-sdk/SKILL.md` (routing table + `references/{config,mcp,troubleshooting}.md`).
