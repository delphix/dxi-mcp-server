# CVE Remediation Report — DLPXECO-14812

**Run:** 2026-10-27  
**Pipeline mode:** pipeline  
**Branch:** dlpx/pr/akshay.kamble/dlpxeco-14812  
**PR:** https://github.com/delphix/dxi-mcp-server/pull/146

## Tickets Fixed

| Ticket | CVE | Package | Old → New | Severity |
|--------|-----|---------|-----------|----------|
| DLPXECO-14812 | CVE-2026-102273 | pyjwt | 2.13.0 → 2.15.1 | HIGH (CVSS 7.4) |

## Vulnerability Details

**CVE-2026-102273** (GHSA-w2cx-738m-mc7w)  
PyJWT accepts public JWK containers as HMAC secrets. An attacker who can supply a public JWK
can forge JWT tokens by having the library treat public key material as the HMAC secret.

- Affected: PyJWT == 2.13.0
- Fixed: PyJWT >= 2.14.0
- Dependency path: mcp[crypto] → pyjwt

## Fix Applied

Updated `pyproject.toml` pin comment to document both CVE-2026-102268 and CVE-2026-102273.
The `pyjwt>=2.14.0` lower-bound was already in place from PR #144 (DLPXECO-14802).
`uv.lock` resolves to pyjwt 2.15.1 which satisfies both CVEs.

No constraint changes were required; only the comment was updated for audit traceability.

## Validation

- `uv sync --extra dev`: passed
- `pre-commit run --all-files` (ruff lint + format): passed
- `pytest tests/ -q -m "not real_dct and not llm_driven and not scenario"`: 855 passed, 947 skipped, 25 deselected

## Jira Updates

- Label added: `mcp-cve-fix-inreview`
- Labels retained: `mcp-cve-triage-done`, `AI-BUGTRIAGE-DONE`
- Status transitioned: In Progress → In Review
- PR comment added with `PR:` prefix for merge tracking
- Remote link added to ticket
