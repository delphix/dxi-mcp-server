# DLPXECO-13635 — Docker Support: Implementation Record

> **Vision**: see [DLPXECO-13635-vision.md](DLPXECO-13635-vision.md)
> **Functional spec**: see [DLPXECO-13635-functional.md](DLPXECO-13635-functional.md)
> **Design**: see [DLPXECO-13635-design.md](DLPXECO-13635-design.md)
> **Domain**: feature
> **Phase**: implement (complete)

---

## Summary

The implement phase realised the design as three commits on
`dlpx/pr/vinay.byrappa/DLPXECO-13635-docker-support`:

1. **`0c86706` — Dockerfile + .dockerignore**
2. **`06405a8` — README "Run with Docker" subsection + TOC**
3. **`12e6359` — `.claude/rules/build-and-execution.md` Docker subsection**

Each commit is a separate logical unit per design §9 and the project's
git-workflow rule ("separate ... config changes from code changes where
possible").

---

## Files changed

| Path | Change | Lines |
|------|--------|-------|
| `Dockerfile` | **CREATE** | 111 |
| `.dockerignore` | **CREATE** | 66 |
| `README.md` | **MODIFY (additive)** | +125 (TOC entry + new subsection) |
| `.claude/rules/build-and-execution.md` | **MODIFY (additive)** | +40 (new subsection) |

**Files NOT changed** (per design §2):
- `src/dct_mcp_server/**` — no source-code changes
- `pyproject.toml`, `requirements.txt` — no dep changes
- `start_mcp_server_*.sh`, `start_mcp_server_*.bat` — host-only, excluded from image
- `.gitignore` — existing exclusions are sufficient

---

## Deviations from design (and why)

### 1. `docs/api-external.yaml` is NOT copied into the image

**Design §2** said `COPY --chown=appuser:appuser docs/api-external.yaml /app/docs/api-external.yaml` to seed the bundled OpenAPI fallback (R3 mitigation), and §4.2 introduced a `docs/**` + `!docs/api-external.yaml` re-include pattern in `.dockerignore`.

**Reality**: the file `docs/api-external.yaml` does **not exist in this
repository**. The `tool_factory.py` fallback path checks
`bundled_path.exists()` and returns `None` gracefully when the file is
absent, so the runtime depends solely on the live download from
`${DCT_BASE_URL}/dct/static/api-external.yaml` — which is the documented
behavior for both host-clone and uvx invocation today.

**Resolution**: dropped the `COPY` line and used the simple `docs/`
exclusion in `.dockerignore`. Container behavior is unchanged from
host-clone (R3 mitigation is moot because the artefact never existed in
the repo). The functional spec's AC-1.4, AC-2.x, R8 still hold; AC-1.10
is satisfied (`docs/` directory absent from `/app`).

This is documented in `.claude/rules/build-and-execution.md` under "Run
with Docker > Notes" so future regenerations of `CLAUDE.md` carry the
context.

### 2. Base-image digest pinned to the actually-pulled tag

Design §3.1 said the implementer "pulls the latest 3.11.x slim-bookworm
and records the digest". Pulled `python:3.11-slim-bookworm` on 2026-05-07
on Apple Silicon via Docker Desktop's `desktop-linux` context:

- Resolved to **Python 3.11.15**
- Digest: `sha256:ee710afcfb733f4a750d9be683cf054b5cd247b6c5f5237a6849ea568b90ab15`

Both `FROM` lines (builder + runtime) reference this exact digest.

### 3. Two `# hadolint ignore=DL3008` comments

Two `RUN apt-get install` invocations carry `# hadolint ignore=DL3008`
because we deliberately do not pin Debian package versions for `tini`
or `build-essential` — reproducibility is governed by the base-image
digest. AC-8.1 permits warnings as long as they are explained inline,
which these are.

### 4. README anchor for `### Run with Docker`

GitHub renders the heading slug as `run-with-docker` (lower-case,
spaces-as-hyphens, no special chars). The TOC link
`[Run with Docker](#run-with-docker)` resolves correctly. Verified by
heading-anchor algorithm and confirmed by visual inspection of the
diff.

---

## Test coverage (from design §6)

All build-time, image-introspection, and doc-lint tests passed during
implementation:

| ID | Status | Evidence |
|----|--------|----------|
| **T-BLD-1** | PASS | `docker build --no-cache --pull` succeeded in ~32 s |
| **T-BLD-2** | PASS | Build context 2.84 kB (« 5 MB) |
| **T-BLD-3** | PASS | 79.0 MB compressed (« 250 MB); 244 MB uncompressed |
| **T-BLD-4** | PASS | `gcc` / `build-essential` absent from runtime image filesystem; `/var/lib/apt/lists/` empty; no pip cache |
| **T-BLD-5** | PASS | All 6 `org.opencontainers.image.*` labels present and correct |
| **T-BLD-6** | PASS | `Healthcheck` is null in `docker inspect` |
| **T-BLD-7** | PASS | `StopSignal` is `"SIGTERM"` in `docker inspect` |
| **T-BLD-8** | PASS | `--platform=linux/amd64` from arm64 host (Apple Silicon) succeeded |
| **T-BLD-9** | PASS | `hadolint/hadolint` exits 0; the two `# hadolint ignore=DL3008` are inline-justified |
| **T-IMG-1** | PASS | `id` inside container reports `uid=1000(appuser) gid=1000(appuser)` |
| **T-IMG-2** | PASS | `/app/.git`, `/app/.claude`, `/app/.venv`, `/app/docs` absent; `/app/logs/sessions` present, owned by appuser |
| **T-IMG-3** | PASS | All 5 toolset `.txt` files + `manual_confirmation.txt` present at expected paths |
| **T-IMG-5** | PASS | No `*.env` / API-key fragments in `docker history` or in image filesystem |
| **T-IMG-6** | PASS | `import dct_mcp_server.main`, `import dct_mcp_server.config.loader`, `import dct_mcp_server.tools` all succeed; toolset directory listed correctly |
| **T-DOC-1** | PASS | `### Run with Docker` exists; TOC entry `- [Run with Docker](#run-with-docker)` exists; depth `###` |
| **T-DOC-3** | PASS | `TODO(DLPXECO-13635)` marker grep-able; placeholder host is `<registry-host>` |
| **T-DOC-4** | PASS | 4 bash + 3 PowerShell + 1 cmd code blocks in section |
| **T-DOC-5** | PASS | "local-development MCP usage" warning sentence present |
| **T-DOC-6** | PASS | `git diff` shows two purely-additive hunks; no edits to existing install content |
| **T-DOC-7** | PASS | `file Dockerfile .dockerignore` reports plain UTF-8 text (no CRLF) |
| **T-DOC-8** | PASS | `git diff --check` is clean |
| **T-DOC-9** | PASS | `.claude/rules/build-and-execution.md` carries new "Run with Docker" subsection |

**T-IMG-4** (api-external.yaml present) is **N/A** — file was not
shipped because it does not exist in the repo (see deviation 1).

The remaining `T-RUN-*` tests require a live DCT instance and an MCP
client and are deferred to the `test` phase.

---

## Coverage matrix (FR/AC → status)

| FR | ACs | Status |
|----|-----|--------|
| FR-1 (Dockerfile builds runnable image) | 1.1..1.10 | PASS — T-BLD-1, T-BLD-3, T-IMG-1, T-IMG-2; AC-1.2..1.6 + 1.8 verified by Dockerfile review |
| FR-2 (parity with local-clone runtime) | 2.1..2.7 | Build-time portions (T-IMG-6) PASS; runtime portions deferred to test phase |
| FR-3 (cross-platform host support) | 3.1..3.5 | T-BLD-8 PASS (amd64 cross-build from arm64); T-RUN-7 + T-RUN-8 deferred |
| FR-4 (README docs) | 4.1..4.7 | T-DOC-1..T-DOC-6 all PASS |
| FR-5 (.dockerignore) | 5.1..5.5 | T-BLD-2 PASS; T-IMG-3 negative check PASS (.txt files NOT excluded) |
| FR-6 (image hygiene) | 6.1..6.8 | T-IMG-1, T-IMG-5, T-BLD-4, T-BLD-5, T-BLD-6 all PASS |
| FR-7 (no host-network deps) | 7.1..7.4 | T-BLD-1 PASS (`--no-cache --pull`); base image + Debian apt mirror + PyPI are the only network endpoints |
| FR-8 (quality / lint / structure) | 8.1..8.4 | T-BLD-9 PASS (hadolint); T-DOC-9 PASS; AC-8.4 — no `pyproject.toml` change |
| QR-1..QR-7 | — | T-DOC-7, T-DOC-8 PASS; QR-3 (no Alpine) honored; QR-6 (fake host) PASS via T-DOC-3 |
| FR-9 (docker-compose) | OPTIONAL — DROPPED | Per design §7 (single-service, stdio-incompatible with `compose up`, YAGNI) |

Every FR has at least one PASSING build-time test or a documented
deferral to the test phase. No FR is unaddressed.

---

## What still needs to happen

The `test` phase performs the live-DCT runtime tests (T-RUN-1..T-RUN-9):

1. Wire the image into Claude Desktop using the README config and verify
   `tools/list` returns the `self_service` toolset (T-RUN-1).
2. Confirm `DCT_TOOLSET=continuous_data_admin` produces 22 tools and
   `DCT_LOG_LEVEL=DEBUG` writes DEBUG output to mounted logs (T-RUN-2).
3. Side-by-side parity against host-clone server: run
   `vdb_tool(action="search")` from both, compare output shapes (T-RUN-3).
4. `DCT_TOOLSET=auto` end-to-end with
   `list_available_toolsets`/`enable_toolset`/`disable_toolset` (T-RUN-4).
5. Mounted `logs/` survives the session and contains UID-1000-owned
   files on Linux (T-RUN-5).
6. Telemetry mount works when opted in (T-RUN-6).
7. Windows host (Docker Desktop + WSL2) using PowerShell `docker run`
   form from README (T-RUN-7).
8. `docker stop` triggers clean lifespan shutdown (T-RUN-8).
9. Confirmation flow works inside container — sample destructive action
   from `.claude/rules/testing/self_service.md` step 56 (T-RUN-9).

The `validate` phase runs the doc-coverage / lint pass against the
merged result.
