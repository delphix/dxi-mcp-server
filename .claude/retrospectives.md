# Feature-Implement Retrospectives

> Lessons-learned log produced by the `feature-implement` retrospective phase.
> Each entry captures one ticket's pipeline run.

---

## DLPXECO-13635 — Run dct-mcp-server in a Docker container

| Field | Value |
|-------|-------|
| Date completed | 2026-05-07 |
| Domain | feature |
| Lite mode | false |
| Worktree | `~/Documents/GitHub/dxi-mcp-server-DLPXECO-13635` |
| Branch | `dlpx/pr/vinay.byrappa/DLPXECO-13635-docker-support` |
| PR | [#69 — DLPXECO-13635 Run dct-mcp-server in a Docker container](https://github.com/delphix/dxi-mcp-server/pull/69) (state: OPEN) |
| Validation verdict | PASS WITH WARNINGS |
| Phases run | context, vision, design, implement, build, test-infra, test, validate, pr, release, retrospective |
| Phases skipped (`--skip`) | none |
| Branch commits | 5 (`0c86706`, `06405a8`, `12e6359`, `3ddfa21`, `f62ac3e`) |

### Reflective questions

1. **What went well?** — Specs paid for themselves at the validate gate: the vision/functional/design split caught two scope drifts before code (the `docs/api-external.yaml` file being assumed to exist when it does not, and `auto` being treated as a 6th toolset `.txt` file when it is actually a programmatic mode in `tools/core/meta_tools.py`). Three logical commits — `Dockerfile + .dockerignore` (`0c86706`), README docs (`06405a8`), contributor rules (`12e6359`) — landed independently per the project's own git-workflow rule, making the PR readable. The validate phase actually validated rather than rubber-stamping: it re-ran the deferred `linux/amd64` cross-build (T-BLD-8 / AC-3.1) that the test phase punted on, captured the digest (`sha256:c83a1549…`), confirmed the size cap (~78.7 MB compressed, well under 250 MB), and re-verified `STOPSIGNAL`/UID-1000/no-`HEALTHCHECK` invariants. Image hygiene held: non-root `appuser` (UID 1000), `tini` PID 1, digest-pinned `python:3.11-slim-bookworm`, no `EXPOSE`, no `HEALTHCHECK`, OCI labels populated, `STOPSIGNAL=SIGTERM`, pip cache absent, no secrets in layers — all seven QR-* quality rules passed. Live DCT smoke worked end-to-end: a Python JSON-RPC harness over Docker stdio exercised `initialize`, `tools/list`, `tools/call` against `https://dct-sho.dlpxdc.co` and observed real VDB results (not just a "container starts" smoke), confirming behavioural parity with the local-clone runtime (G5 from vision). The orchestrator correctly detected the existing worktree (`_GIT_COMMON != _GIT_DIR`) and skipped re-creating one, so all work stayed isolated under `~/Documents/GitHub/dxi-mcp-server-DLPXECO-13635/` and `main` was never polluted.

2. **What was harder than expected?** — Test-plan drift: two test items (T-IMG-3 expected 6 toolset `.txt` files, T-IMG-4 expected the bundled spec to be present) were stale by the time the test phase ran because the design had already moved away from bundling the spec, and `auto` had never been a `.txt` file. The validate phase corrected the expectations but the cleaner fix is to regenerate the test-plan from the design after every design revision. Cross-platform `linux/amd64` was deferred from test → validate because the developer's host was Apple Silicon (`linux/arm64`); the test phase should explicitly run `docker buildx build --platform=linux/amd64` even when the host is arm64, rather than punting. Windows host smoke is still owed (T-RUN-7 / AC-3.3 / AC-3.5): the PowerShell and `cmd.exe` snippets were syntax-reviewed but never actually executed against a real Windows 11 + Docker Desktop + WSL2 host, listed as the single High in the validation report. Three pre-existing `main`-branch behaviours surfaced during testing and had to be carved out as "not Docker regressions": `DCT_LOG_LEVEL=DEBUG` not propagating to the file logger, `continuous_data_admin` showing 21 tools at runtime when startup logs say 22, and `auto.md` documenting 5 meta-tools when reality is 6 (`execute_action` is the extra). Each is a follow-up ticket. Lesson: when a feature involves repackaging existing code, you discover existing bugs — flag them, do not silently fix them in the same PR. The `docs/api-external.yaml` design assumption was wrong: design §2 specified `COPY docs/api-external.yaml` but the file does not exist in the repo; the implementer correctly dropped the `COPY` and relied on the runtime download path. Lesson: design phase should grep-verify every file path it references before declaring it as a `COPY` source.

3. **What would I do differently next time?** — Run `--platform=linux/amd64` in the test phase, not validate: when the developer's host arch is arm64, the test phase should still cross-build the canonical arch with `docker buildx`. Treating this as a validate-only check creates a single point of failure at the gate; if validate is skipped, the canonical arch is never exercised. Grep-verify every file path in the design before committing it — the `docs/api-external.yaml` mistake was a one-line check away (`find . -name api-external.yaml` would have caught it). Plan the Windows smoke earlier in the run: T-RUN-7 was deferred from test → validate → "owed before close"; each handoff is a chance to lose the trail. For features that explicitly target Windows, the test-infra phase should provision a Windows VM up front (or fail loudly that no Windows host is available) so the verification is forced rather than negotiated. Regenerate the test-plan after design changes: when design §7 dropped FR-9 (`docker-compose`) and §2 inverted the bundled-spec assumption, the test-plan should have been regenerated from the new design. The cost was three Medium-severity test-plan corrections in the validate report. Open follow-up tickets immediately when a non-regression issue is observed: the three `main`-branch issues (DEBUG logging, 21-vs-22 tools, 6-vs-5 meta-tools) were correctly flagged as out-of-scope but were not yet ticketed at retrospective time — convert each to a Jira issue today, not "soon". Finally, accept that gate handbacks (vision → design → implement) are the cost of safety, but consider an opt-in `--auto-advance` mode for trusted users on low-risk changes.

---

### What went well — detailed

- **Specs gated the gates.** The vision/functional/design split caught two scope drifts before code: (a) `docs/api-external.yaml` being assumed to exist in the repo when it does not, and (b) `auto` being treated as a 6th toolset `.txt` file when it is actually a programmatic mode. Both surfaced as test-plan deviations rather than bugs because the design phase forced explicit enumeration of files-to-modify.
- **Three logical commits, not one fat one.** `Dockerfile + .dockerignore` (`0c86706`), README docs (`06405a8`), and contributor rules (`12e6359`) landed as separate commits. This made the PR readable and matches the project's own git-workflow rule ("Separate toolset config changes from code changes where possible").
- **Validate phase actually validated, not rubber-stamped.** It re-ran the deferred `linux/amd64` cross-build (T-BLD-8 / AC-3.1) that the test phase punted on, captured the digest (`sha256:c83a1549…`), confirmed the size cap (~78.7 MB compressed), and re-verified `STOPSIGNAL`/UID/no-`HEALTHCHECK` invariants. Without this re-run AC-3.1 would have shipped unverified.
- **Image hygiene held.** Non-root `appuser` (UID 1000), `tini` PID 1, digest-pinned `python:3.11-slim-bookworm`, no `EXPOSE`, no `HEALTHCHECK`, OCI labels populated, `STOPSIGNAL=SIGTERM`, pip cache absent, no secrets in layers. All seven QR-* quality rules passed.
- **Live DCT smoke worked end-to-end.** The Python JSON-RPC harness over Docker stdio exercised `initialize`, `tools/list`, `tools/call` against `https://dct-sho.dlpxdc.co` and observed real VDB results — not just a "container starts" smoke. Confirms behavioural parity with the local-clone runtime (G5 from vision).
- **Worktree isolation worked.** All work happened in `~/Documents/GitHub/dxi-mcp-server-DLPXECO-13635/`; `main` was never polluted; the orchestrator correctly detected the existing worktree (`_GIT_COMMON != _GIT_DIR`) and skipped re-creating one.

### What was harder than expected — detailed

- **Test-plan drift.** Two test items (T-IMG-3 expected 6 toolset `.txt` files; T-IMG-4 expected the bundled spec to be present) were stale by the time the test phase ran. The validate phase corrected the expectations but the cleaner fix is to regenerate the test-plan from the design after every design revision.
- **Cross-platform `linux/amd64` build was deferred from test → validate.** The test phase ran on Apple Silicon (`linux/arm64`) and could not exercise AC-3.1 directly. This is a recurring pattern when the developer's host arch differs from the canonical target arch.
- **Windows host smoke is still owed (T-RUN-7 / AC-3.3 / AC-3.5).** PowerShell and `cmd.exe` snippets were syntax-reviewed but never actually executed against a real Windows 11 + Docker Desktop + WSL2 host. Listed as the single High in the validation report.
- **Three pre-existing `main`-branch behaviours surfaced during testing** and had to be explicitly carved out as "not Docker regressions": (a) `DCT_LOG_LEVEL=DEBUG` not propagating to the file logger, (b) `continuous_data_admin` showing 21 tools at runtime when startup logs say 22, (c) `auto.md` documenting 5 meta-tools when reality is 6. Each is a follow-up ticket.
- **`docs/api-external.yaml` design assumption was wrong.** Design §2 specified `COPY docs/api-external.yaml` to seed the bundled fallback; the file does not exist in the repo. The implementer correctly dropped the `COPY` and relied on the runtime download path.
- **Re-running orchestrator after each gate is friction.** Each gate handback (vision → design → implement) requires a fresh `/feature-implement <ticket> --step <next>` invocation. By design, but for trusted users on low-risk changes an "auto-advance through gates" mode would help.

### Surprises

- **Image came in much smaller than the budget.** Vision §7 set ≤ 250 MB compressed; reality was ≈ 78.7 MB compressed (≈ 230 MB uncompressed) — 30% of the cap. Multi-stage `python:3.11-slim-bookworm` + `--no-install-recommends` + `PIP_NO_CACHE_DIR=1` + `.dockerignore` together did most of the work; no aggressive size optimisation was needed.
- **macOS UID mapping anomaly is by design, not a bug.** Mounted log file appeared as `uid=502` (host user) on macOS instead of `uid=1000` (container `appuser`). This is Docker Desktop's gRPC-FUSE / VirtioFS user-namespace mapping. On a Linux native bind mount it would be 1000:1000.
- **`docker stop` shutdown was 140 ms.** With `tini` as PID 1 and FastMCP's lifespan-finally block running, signal forwarding was effectively instant. The 12-second `STOPTIMEOUT` budget was never exercised.
- **Hadolint passed cleanly** with only two well-justified `# hadolint ignore=DL3008` annotations (intentional unpinned `tini` install).
- **Build context was 2.84 kB** — `.dockerignore` is doing serious work.
- **Auto-mode meta-tool drift exists on `main`.** `auto.md` expects 5 meta-tools; the running server registers 6. Pre-existing, not introduced by this run.

### Pipeline metrics

- **Phases**: 11 of 11 ran (all gates satisfied; no `--skip`).
- **Phases auto-completed in this orchestrator session**: 1 (retrospective). All prior phases ran in earlier sessions, gated by manual user re-invocation.
- **Duration (calendar)**: same-day pipeline (`2026-05-07`).
- **Commits on feature branch**: 5 — three implementation commits (`0c86706`, `06405a8`, `12e6359`) + two artefact commits (`3ddfa21`, `f62ac3e`).
- **Files modified vs. baseline `main`**: 4 (`Dockerfile`, `.dockerignore`, `README.md`, `.claude/rules/build-and-execution.md`); 0 under `src/`.
- **FR coverage**: 8 PASS, 0 FAIL, 1 N/A (FR-9 dropped per design §7).
- **Test results**: 16 PASS, 0 FAIL, 1 SKIP (Windows manual), several DEFER closed by validate.
- **Validation verdict**: PASS WITH WARNINGS (1 High = Windows smoke owed; 5 Medium = mostly pre-existing `main` issues + test-plan drift).
- **Hadolint**: PASS (exit 0; 2 justified ignores).
- **Image facts**: linux/amd64, 230 MB uncompressed / 78.7 MB compressed, non-root `appuser` (UID 1000), `tini` PID 1, `STOPSIGNAL=SIGTERM`, no `EXPOSE`, no `HEALTHCHECK`, all 6 OCI labels.
- **`docker stop` shutdown latency**: 140 ms (vs. 12 s STOPTIMEOUT budget).
- **PR**: #69 OPEN.

### Outstanding work after merge

| Priority | Item | Owner |
|----------|------|-------|
| High | Run T-RUN-7 (Windows 11 + Docker Desktop + WSL2 + Claude Desktop smoke) and append §6 to `docs/DLPXECO-13635-test-evidence.md`. | Tester with Windows host |
| Medium | Update `docs/DLPXECO-13635-test-plan.md` T-IMG-3 expected list (5 toolset `.txt` files, drop `auto`). | Author of next housekeeping commit |
| Medium | Update `docs/DLPXECO-13635-test-plan.md` T-IMG-4 to assert *absence* of bundled `docs/api-external.yaml` plus startup-log download line. | Author of next housekeeping commit |
| Medium | Open follow-up ticket: `DCT_LOG_LEVEL=DEBUG` not honoured by file logger (pre-existing on `main`). | Backlog |
| Medium | Open follow-up ticket: `continuous_data_admin` 21-vs-22 tool count drift (pre-existing on `main`). | Backlog |
| Medium | Open follow-up ticket: `auto.md` says 5 meta-tools, runtime has 6 (`execute_action`) — reconcile docs or remove the meta-tool. | Backlog |
| Low | When the registry is provisioned, replace `<registry-host>` placeholder in `README.md` (grep for `TODO(DLPXECO-13635)`). | Whoever provisions the registry |
| Low | When `pyproject.toml` version is bumped, update `org.opencontainers.image.version` label in `Dockerfile:60` in the same commit. | Future release author |

### Skills used

- `superpowers:using-git-worktrees` — orchestrator-side, ensured all work was isolated under `dxi-mcp-server-DLPXECO-13635/` and main branch was never touched.
- `superpowers:writing-plans` — design phase produced an explicit per-task plan with file paths.
- `superpowers:test-driven-development` — test-plan was authored before implement; test phase produced evidence against it.
- `superpowers:requesting-code-review` (pending PR review) — PR #69 is OPEN awaiting reviewers.
- Inline fallbacks were not needed; all referenced superpowers were available.

### One-line takeaway

Specs gated the gates: the design forced the implementer to enumerate every changed file, the test plan forced explicit coverage assertions, and the validate phase closed the deferred cross-build before letting the PR ship — exactly the value proposition of the spec-driven pipeline.
