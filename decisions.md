# Decisions

> Scope: project-local — this file governs only this project root. Cross-project truth lives in the 2nd Brain vault: /Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain (contract: 00 - System/contracts/project-link-bridge.md).

Use this file for durable choices, supersession, reversals, and rationale.
Keep execution proof in `progress.md` or `vault/sessions/`.

| ID | Date | Decision | Status | Rationale | Evidence | Supersedes |
| --- | --- | --- | --- | --- | --- | --- |
| D-001 | 2026-09-03 | Use V.A.U.L.T. owner-doc structure for project continuity | accepted | Future agents need one owner per truth type | `VAULT.md`, `FILE_MAP_INDEX.md` | - |
| D-002 | 2026-09-03 | Fail-open multi-provider cascade with 'use or skip' semantics | accepted | Autonomous AI agents must never crash on search quota exhaustion or 429/403/timeout | `search_sdk/client.py`, `tests/test_cascade.py` | - |
