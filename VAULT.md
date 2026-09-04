# PROJECT VAULT - 26.09.03-agent-search-sdk

> Scope: project-local — this file governs only this project root. Cross-project truth lives in the 2nd Brain vault: /Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain (contract: 00 - System/contracts/project-link-bridge.md).

> Current-state router. Read `AGENTS.md` first for operating rules, then use
> this file to find the active owner docs.

## Snapshot

- Project: 26.09.03-agent-search-sdk
- Summary: The canonical web-search wheel for local agents — Python SDK, CLI `agent-search`, and MCP server over one configurable fail-open cascade (Brave → Tavily → SerpApi pool → self-hosted SearXNG → residential proxy → DuckDuckGo) with RRF fusion, a settings file, credential auto-discovery with provenance, and `doctor`. Supersedes `web-search-manager`.
- Current phase: v1.1.0 shipped 2026-09-04; public repo `https://github.com/vecyang1/agent-search-sdk`
- Last updated: 2026-09-04 by Claude (Claude Code) — debug pass, settings layer, honest tests
- Health: GREEN — hermetic 86/86, live 9/9, doctor 6/6, MCP e2e answered (see `progress.md`)

## Current Goal

- North star: any agent on this machine gets a search result or an honest skip list, never a crash, through one entry point that other agents can discover (skill `agent-search-sdk`, `mcp_registry.md`).
- Near-term outcome: keep the live suite honest and the fixtures current; extend by adding providers to the registry rather than forking scripts.
- Constraints: free-tier quotas (Brave 1 req/s, 1k/mo; Tavily 1k/mo; SerpApi pooled), DuckDuckGo bot challenges, AGPL-3.0 public repo (never commit `.env`).

## Source Pointers

| Truth Type | Owner |
| --- | --- |
| Project rules | `AGENTS.md` |
| Public start page | `README.md` |
| System architecture and module/data/integration map | `docs/architecture.md` |
| Current state, source pointers, and risks | `VAULT.md` |
| Active/backlog tasks with Created/Updated dates | `task_plan.md` |
| Dated execution evidence | `progress.md` |
| Latest resume card | `handoff.md` |
| Durable decisions | `decisions.md` |
| Release notes | `CHANGELOG.md` |
| Folder and document boundaries | `FILE_MAP_INDEX.md` |
| Health checks and what each proves | `operations/health-checks.md` |
| Skill routes and skills used | `AGENTS.md` for skill roots; `progress.md` for the canonical skills-called log |
| Global skill (discovery for other agents) | `~/.gemini/antigravity/skills/agent-search-sdk/SKILL.md` (+ `references/`) |
| Stable cross-project memory | 2nd Brain `05 - Memory Center` only when reusable outside this project |
| Cross-project router | 2nd Brain project index `00 - System/registries/project-index.md` |

## Current Risks

- DuckDuckGo Lite HTTP 202 anomaly challenge is external and intermittent; the live test skips only on that exact condition (`tests/test_live.py`).
- Brave 429 when two callers overlap; runbook says run live checks sequentially.
- `web-search-manager/src/server.py` may still be registered somewhere as an MCP; remove that registration then the folder (`decisions.md` D-007).
- Global MCP registration for `agent-search` not applied (user decision).

## Next Actions

1. Decide on global MCP registration (`references/mcp.md` snippet).
2. Remove `web-search-manager` once no client points at its `src/server.py`.
3. When a provider drifts: re-capture fixture → failing test → fix (`docs/architecture.md` Update Triggers).

## Do Not

- Do not store raw evidence in polished docs; use `vault/`.
- Do not move local project evidence into the global 2nd Brain Memory Center.
- Do not duplicate decisions across `VAULT.md` and `decisions.md`.
- Do not claim completion without fresh verification recorded in `progress.md`.
- Do not add a search script elsewhere; add a provider here.
