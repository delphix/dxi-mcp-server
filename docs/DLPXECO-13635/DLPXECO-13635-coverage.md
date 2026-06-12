# Spec-Code Coverage: DLPXECO-13635

| FR-ID | Description | Status | Evidence (file:line or "none") |
|-------|-------------|--------|-------------------------------|
| FR-001 | Dockerfile for Containerised DCT MCP Server Runtime | PASS | .claude/test/generated-test/test_DLPXECO-13635.py:80 (`test_s1_docker_build_succeeds`); :136 (`test_s3_runtime_user_is_appuser`); :164 (`test_s4_package_imports_correctly`); :188 (`test_s5_missing_creds_produces_descriptive_error`) |
| FR-002 | .dockerignore for Lean Build Context | PASS | .claude/test/generated-test/test_DLPXECO-13635.py:38 (`DOCKERIGNORE = REPO_ROOT / ".dockerignore"`); :209 (`test_s6_sensitive_paths_absent_from_image`); :262 (`test_s8_test_and_eval_dirs_absent_from_image`) |
| FR-003 | README "Run with Docker" Documentation Section | PASS | .claude/test/generated-test/test_DLPXECO-13635.py:497 (`test_s15_readme_run_with_docker_section`); :498 ("README contains 'Run with Docker' section with bash, PowerShell, and cmd.exe") |
| FR-004 | Windows Compatibility for Docker Stdio Transport | PASS | .claude/test/generated-test/test_DLPXECO-13635.py:521 (`test_s16_readme_docker_flags`); :303 (`-i`, `--init` flags used in S9 test); :586 (`test_s18_no_minus_i_exits_immediately`) |
| FR-005 | Registry Placeholder and Future Distribution Path | PASS | .claude/test/generated-test/test_DLPXECO-13635.py:559 (`test_s17_registry_placeholder`); :567 (`assert "<registry-host>" in content`) |
