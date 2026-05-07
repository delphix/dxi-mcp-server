# DLPXECO-13635 — Build Output

## Build Result

**Command**: `docker build -t dct-mcp-server:dev .`
Exit code: 0

**Project type**: standard (Python; no monorepo markers — single `pyproject.toml`, single `requirements.txt`, single source tree under `src/dct_mcp_server/`).

**Build host**: Docker 29.1.1 (server 29.3.1), `desktop-linux` builder, target platform `linux/arm64` (build host arch).

**Image facts (post-build)**:

| Property | Value |
|----------|-------|
| Repository:tag | `dct-mcp-server:dev` |
| Image ID | `sha256:97188a0e0617e8afe7780da102ae3996e1f374d8384e2c3d1db1e5dc0894a14e` |
| Reported size | 269 MB (uncompressed, `docker images`) |
| User | `appuser` (non-root, UID/GID 1000) |
| Entrypoint | `["/usr/bin/tini", "--"]` |
| Default Cmd | `["python", "-m", "dct_mcp_server.main"]` |
| StopSignal | `SIGTERM` |
| WorkingDir | `/app` |

These values match the design contract in `docs/DLPXECO-13635-design.md` §3 and the runtime facts documented in `.claude/rules/build-and-execution.md`.

---

## Last lines of build output

```
#16 DONE 0.5s

#17 [runtime 6/8] COPY --chown=appuser:appuser src/ /app/src/
#17 DONE 0.0s

#18 [runtime 7/8] COPY --chown=appuser:appuser pyproject.toml requirements.txt /app/
#18 DONE 0.0s

#19 [runtime 8/8] RUN mkdir -p /app/logs/sessions     && chown -R appuser:appuser /app
#19 DONE 0.2s

#20 exporting to image
#20 exporting layers
#20 exporting layers 0.5s done
#20 writing image sha256:97188a0e0617e8afe7780da102ae3996e1f374d8384e2c3d1db1e5dc0894a14e
#20 writing image sha256:97188a0e0617e8afe7780da102ae3996e1f374d8384e2c3d1db1e5dc0894a14e done
#20 naming to docker.io/library/dct-mcp-server:dev done
#20 DONE 0.5s
```

---

## Notes

- This feature ships a **container image build** as its primary deliverable (Docker support); there is no compiled artefact for the underlying Python source — `pip install` of `requirements.txt` happens inside the `builder` stage and the resulting `/opt/venv` is copied into the slim runtime image.
- No automated unit-test suite exists in this repo (per CLAUDE.md). Functional verification — running the image with a real `DCT_API_KEY` / `DCT_BASE_URL` and exercising MCP toolsets — is owned by the `test-infra` and `test` phases that follow this gate.
- Cached re-run (no source changes) completes in <1 s, exit 0, producing the identical image digest. This confirms the build is deterministic across invocations.
