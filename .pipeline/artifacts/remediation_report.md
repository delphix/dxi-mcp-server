# CVE Remediation Report — DLPXECO-14802

**Run date:** 2026-10-27  
**Ticket:** [DLPXECO-14802](https://perforce.atlassian.net/browse/DLPXECO-14802)  
**PR:** https://github.com/delphix/dxi-mcp-server/pull/144

## Summary

| Ticket | CVE | GHSA | Package | Old Version | New Version | Severity |
|--------|-----|------|---------|-------------|-------------|----------|
| DLPXECO-14802 | CVE-2026-102268 | GHSA-ffc3-869f-jxw9 | PyJWT | 2.13.0 | 2.15.1 | Critical |

## Vulnerability Details

**CVE-2026-102268** — PyJWT asymmetric-PEM detection bypass.

PyJWT <= 2.13.0 contains a flaw where whitespace or line-ending mutations in
public keys cause the HS/asymmetric confusion guard to be skipped. This allows
an attacker to use a public key as an HMAC secret to forge JWT signatures,
completely bypassing signature verification.

PyJWT is a transitive dependency via `mcp[crypto]`.

## Fix Applied

- Added `pyjwt>=2.14.0` to `[project].dependencies` in `pyproject.toml` with a CVE comment
- Ran `uv lock --upgrade-package pyjwt` — lock now resolves pyjwt==2.15.1

## Validation

- `uv sync --extra dev`: pyjwt 2.13.0 → 2.15.1 installed, no resolver conflicts
- `pytest tests/ -q -m "not real_dct and not llm_driven and not scenario"`: **855 passed, 0 failed**
- `uv.lock` confirms: `name = "pyjwt"` / `version = "2.15.1"` (>= patched 2.14.0)

## Jira State Change

- Added label: `mcp-cve-fix-inreview`
- Kept triage labels: `mcp-cve-triage-done`, `AI-BUGTRIAGE-DONE`
