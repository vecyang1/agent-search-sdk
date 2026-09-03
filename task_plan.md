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

## Backlog

| ID | Priority | Created | Updated | Task | Why It Matters | Link |
| --- | --- | --- | --- | --- | --- | --- |
| T-002 | medium | 2026-09-03 | 2026-09-03 | Add project-specific verification commands | Future agents need proof before claiming completion | `operations/README.md` |

## Rollover Rule

When this file reaches roughly 80-120 task rows or roughly 60 completed/dropped
rows, move older closed rows to `99 - Archive/task-ledger/YYYY-completed-tasks.md`
or the project's chosen archive owner, then leave a pointer here.
