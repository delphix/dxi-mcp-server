# Layer 5 — LLM-driven E2E (Claude Code CLI)

Advisory, local-only tests that answer a question no scripted layer can: **given only
a plain-English task and the tool schemas, can Claude discover the right tool, call it
correctly, and did the operation actually take effect on a real DCT?**

The driver is the headless **Claude Code CLI** — there is no local-LLM alternative.
It authenticates with your existing Claude session (no metered API key), and runs:

```
claude -p "<task>" \
  --mcp-config <temp dct.json>  \
  --strict-mcp-config \
  --allowedTools "mcp__delphix-dct__*" \
  --permission-mode bypassPermissions \
  --append-system-prompt-file .claude/test/llm-driver-preprompt.md \
  --output-format stream-json --verbose
```

The tests parse the `stream-json` tool-call trace and assert on which tools/actions
Claude chose, then verify the real effect.

## Prerequisites

- `claude` (Claude Code CLI) on PATH and logged in.
- A **real, disposable** DCT — localhost dev instance or a cloned DCT. `DCT_BASE_URL`
  and `DCT_API_KEY` in the environment.
- Tests skip cleanly if any prerequisite is missing — they never fail the suite.

## Running

```bash
# Read-only discoverability smoke (safe):
dct-mcp-test --layer llm --base-url https://localhost --api-key <key>

# Include the mutating act -> verify provision test (disposable DCT only):
LLM_ALLOW_MUTATION=1 dct-mcp-test --layer llm --base-url https://localhost --api-key <key>
```

Or directly:

```bash
DCT_BASE_URL=... DCT_API_KEY=... pytest tests/llm_local -v -m llm_driven
```

## What's here

| File | Purpose |
|---|---|
| `conftest.py` | `llm_driver` fixture — runs `claude -p` and parses the tool-call trace |
| `test_ai_usability_smoke.py` | Read-only discoverability: did Claude pick `vdb_tool`/`job_tool`? |
| `test_provision_verify.py` | Full **act → wait-for-job → verify** (gated behind `LLM_ALLOW_MUTATION=1`) |

## The act → verify contract

Every test confirms the **real effect**, not just a non-error tool response. Async DCT
operations (provision, refresh, snapshot, delete) return a *job*; the job-completion
pre-prompt makes Claude poll `job_tool` to a terminal state before declaring success,
and verification reads fresh state through an independent call. See
[`.claude/test/testing.md`](../../.claude/test/testing.md) and
[`.claude/test/llm-driver-preprompt.md`](../../.claude/test/llm-driver-preprompt.md).
