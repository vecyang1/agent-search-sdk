# Task Plan

> Active and near-term work only. Keep this file small; archive old
> completed/dropped rows before it becomes a giant database.
> Every task row includes `Created` (first entered into this ledger) and
> `Updated` (last change to the row, status, or evidence), both as `YYYY-MM-DD`.

## Active

| ID | Status | Created | Updated | Task | Owner | Next Action | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `AS-T001` | done | 2026-09-03 | 2026-09-03 | Scaffold V.A.U.L.T. structure & governance | Agent | Verified via audit | `init_vault.py --audit` |
| `AS-T002` | done | 2026-09-03 | 2026-09-03 | Multi-provider Search SDK with 'use or skip' cascade | Agent | 5 providers integrated | `search_sdk/client.py`, `search_sdk/providers/` |
| `AS-T003` | done | 2026-09-03 | 2026-09-03 | Standalone CLI `agent-search` and `doctor` suite | Agent | Verified with live probe | `bin/agent-search` |
| `AS-T004` | done | 2026-09-03 | 2026-09-03 | Unit tests and live integration test suite | Agent | 14/14 unit, 4/4 live passing | `run_tests.py`, `tests/test_live.py` |
| `AS-T005` | done | 2026-09-03 | 2026-09-03 | FastMCP JSON-RPC server and global skill bridge | Agent | Skill and MCP exposed | `search_sdk/mcp_server.py`, `skills/agent-search-sdk/` |
| `AS-T006` | done | 2026-09-03 | 2026-09-03 | Push to GitHub public repo and Notion Product[OS] registry | Agent | Notion page & GitHub live | `https://github.com/vecyang1/agent-search-sdk`, `3d0e1b43-2393-81b1-bcb0-c52943895b66` |
| `AS-T007` | done | 2026-09-04 | 2026-09-04 | Real-page debug pass: DDG ads/entities/anomaly, Brave bool date, MCP entry, 1Password cache poisoning | Claude | shipped in v1.1.0 | `progress.md` 2026-09-04, `tests/fixtures/` |
| `AS-T008` | done | 2026-09-04 | 2026-09-04 | Settings layer + `agent-search config` + shared HTTP transport (Retry-After) + credential provenance in `doctor` | Claude | shipped | `search_sdk/settings.py`, `search_sdk/http.py`, `tests/test_settings.py`, `tests/test_http.py` |
| `AS-T009` | done | 2026-09-04 | 2026-09-04 | Honest tests: sandbox owner, process-level CLI + MCP, coverage gates, live suite with `on_error=raise` | Claude | 86 hermetic / 9 live green | `run_tests.py`, `tests/test_gate_coverage.py`, `tests/test_live.py` |
| `AS-T010` | done | 2026-09-04 | 2026-09-04 | Consolidate wheels: supersede `web-search-manager`, register MCP in `mcp_registry.md`, skill routing table + references | Claude | write-backs done | `~/.gemini/antigravity/skills/agent-search-sdk/`, `mcp_registry.md`, `installation_log.md` |

## Backlog

| ID | Priority | Created | Updated | Task | Why It Matters | Link |
| --- | --- | --- | --- | --- | --- | --- |
| T-002 | done | 2026-09-03 | 2026-09-04 | Add project-specific verification commands | Future agents need proof before claiming completion | `operations/health-checks.md` |
| T-003 | low | 2026-09-04 | 2026-09-04 | Register `agent-search` MCP globally (user decision; persistent config change) | One MCP entry for every agent harness | skill `references/mcp.md` |
| T-004 | low | 2026-09-04 | 2026-09-04 | Retire `web-search-manager` folder once no client references `src/server.py` | Remove the last duplicate wheel | `decisions.md` D-007 |

## Rollover Rule

When this file reaches roughly 80-120 task rows or roughly 60 completed/dropped
rows, move older closed rows to `99 - Archive/task-ledger/YYYY-completed-tasks.md`
or the project's chosen archive owner, then leave a pointer here.
