# Spec-Code Coverage: DLPXECO-13635

| FR-ID | Description | Status | Evidence (file:line or "none") |
|-------|-------------|--------|-------------------------------|
| FR-001 | Fix Logging Path Detection for Installed-Package Environments (`_get_project_root`, `site-packages` guard, `PermissionError` graceful degradation) | PASS | `src/dct_mcp_server/core/logging.py:138` — `_get_project_root` definition; `.claude/test/generated-test/test_DLPXECO-13635.py:4` — test coverage note; `src/dct_mcp_server/core/logging.py:95` — `PermissionError` handler |
| FR-002 | Dockerfile — Minimal Non-Root Container Image (`mcpuser`, UID 1000, non-root) | PASS | `.claude/test/generated-test/test_DLPXECO-13635.py:302` — `test_s7_container_runs_as_mcpuser`; `Dockerfile:5` — `groupadd mcpuser` / `useradd --uid 1000` |
| FR-003 | `.dockerignore` — Lean Build Context (excludes `docs/`, `.claude/`, `.git/`) | PASS | `.claude/test/generated-test/test_DLPXECO-13635.py:385` — `test_s11_build_context_excludes_dev_dirs`; `.dockerignore:1` — exclusion rules |
| FR-004 | `docker-compose.yml` — Local Development Convenience (`docker compose up`, `.env` required) | PASS | `.claude/test/generated-test/test_DLPXECO-13635.py:401` — `test_s12_docker_compose_up_with_env_file`; `docker-compose.yml:1` — compose file |
| FR-005 | `README.md` — Docker Section (`## Running with Docker` section, ToC link, env var examples) | PASS | `.claude/test/generated-test/test_DLPXECO-13635.py:183` — `test_s14_toc_entry_present`; `README.md` — `## Running with Docker` section confirmed present |
