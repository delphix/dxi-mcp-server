# Contributing to dxi-mcp-server

Thank you for your interest in contributing. Please read the sections below before opening a pull request.

## Getting Started

1. Fork the repository and create a branch from `main` using the naming convention `dlpx/pr/<username>/<description>`.
2. Make your change. Keep commits focused — separate config/toolset changes from source code changes where possible.
3. Open a pull request against `main`. Include what changed, why, and how it was tested (MCP client used, toolset, DCT version).

For the full contributor agreement and code of conduct, see [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md).

## Test Coverage

### Current threshold

The `test` job in `.github/workflows/ci.yml` enforces a minimum line-coverage floor via:

```
pytest --cov=src/dct_mcp_server --cov-fail-under=4
```

Current floor: **4%**. Target: **80%**.

A pull request that drops measured coverage below the floor will fail the `test` CI job and cannot be merged until coverage is restored.

### Ratchet schedule

The floor is raised incrementally each sprint as new tests are added. The planned milestones are:

| Sprint | Floor | Tracking ticket |
|--------|-------|-----------------|
| S2 (baseline) | 4% | DLPXECO-14016 |
| S3 | ~15% | TBD |
| S4 | ~30% | TBD |
| S5 | ~50% | TBD |
| S6+ | ~80% | TBD |

### How to raise the floor (ratchet ticket authors)

When a ratchet ticket lands, update **both** of the following files in the same commit:

1. **`.github/workflows/ci.yml`** — change `--cov-fail-under=<old>` to `--cov-fail-under=<new>`.
2. **`CONTRIBUTING.md`** (this file) — update the "Current floor" value above and add a row to the ratchet schedule table.

Keeping both files in sync ensures contributors always see the correct threshold in documentation and that CI enforces it. A PR that raises only one of the two files will be rejected during review.
