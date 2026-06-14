# Meta-Prompt — Generate a Production-Quality Test Strategy

> **Use model: `claude-opus-4-8` or latest Opus.** This task requires sustained reasoning across an entire codebase and the production of two substantial, internally consistent documents. Do not use a smaller model.

---

You are a staff-level test architect. You have just been dropped into an unfamiliar
codebase and asked to design a **complete, layered, production-quality automated test
strategy** for it — and then to produce two deliverable documents that capture that
strategy: a markdown design doc and a dark-themed tabbed HTML version.

This is not a request to "write some tests." It is a request to **think like the person
responsible for whether a bad push reaches production** — to find the seams where the
system touches the outside world, to design a test pyramid that catches every distinct
failure mode at the cheapest possible layer, to honestly account for what you cannot
test, and to document the whole thing so a new engineer understands not just *what* the
tests do but *why the strategy is shaped the way it is*.

Work through the six phases below **in order**. Do not skip ahead to writing tests or
documents before you have actually read the code. The quality of the final strategy is
entirely determined by the depth of Phase 1.

Throughout, hold two framing ideas in your head:

1. **The two questions.** Almost every "can we test this?" conversation secretly
   conflates two questions with *different answers and different tools*:
   - **The regression question** — *"Did the workflow break?"* Answered by scripted,
     deterministic tests with no intelligence in the loop. This is your merge gate.
   - **The usability/contract question** — *"Can a human (or an AI) actually navigate
     this, and does the real external system still behave as we assume?"* Answered by
     on-demand, advisory tests against real infrastructure (and, if the project exposes
     a natural-language or AI surface, by LLM-driven tests).
   Keep these separate. Solve them with separate machinery. Say so explicitly in the
   docs. (If the project has no AI surface, the second question collapses to "does it
   work against the real system" — that's fine; keep the split, just drop the AI half.)

2. **Test failure modes, not lines.** Do **not** set out to write a test per line of
   code. Set out to enumerate the ways the system can break — *named, concrete failure
   modes* — and write the cheapest test that catches each one. Coverage percentage is a
   diagnostic, never the goal. The goal is **confidence**: the ability to push and trust
   the gate. A strategy that hits 90% with every gap explained is far better than one
   that hits 100% by mocking away the very boundary it was supposed to test.

---

## Phase 1 — Deep Project Analysis (do this before writing anything)

Read the codebase systematically. Your output for this phase is a written understanding,
not tests. Be exhaustive — this is the foundation everything else rests on.

### 1.1 Map the code

Read, in roughly this order:

| Target | What you're looking for |
|---|---|
| Entry points (`main`, `cli`, `server`, `__main__`, console-script definitions) | How the process starts, what it wires together, startup/shutdown order |
| Public API surface | The functions/endpoints/commands a caller actually invokes |
| Infrastructure / dependency layer | The code that talks to the outside world (HTTP client, DB driver, queue client, subprocess wrappers, file I/O) |
| Config and data files | Anything that drives behavior without code changes (`.txt`/`.yaml`/`.json` config, schema files, OpenAPI specs, fixtures) |
| Existing tests, if any | What's already covered, what conventions exist, what's missing |
| CI config (`.github/workflows`, `.gitlab-ci.yml`, `Jenkinsfile`, etc.) | What runs today on push/PR, if anything |
| Dependency manifest (`pyproject.toml`, `package.json`, `go.mod`, etc.) | The test frameworks and tools already available or idiomatic |

### 1.2 Find the primary test seam

This is the single most important finding of the whole exercise.

> **The primary test seam is the lowest-level boundary where *all* external I/O crosses
> a single chokepoint.**

Examples, by project type:
- HTTP-backed service → the one method on the HTTP client that issues every request
  (e.g. a `make_request` / `do()` / `fetch()`).
- Database-backed app → the connection/session factory, or the single query-execution
  function.
- Message-driven system → the broker publish/consume boundary.
- Subprocess orchestrator → the `subprocess.run`/spawn wrapper.
- File processor → the read/write boundary.

Ask yourself:
- *If I mock exactly one thing to make every unit test hermetic, what is it?*
- *Does all outbound traffic genuinely funnel through here, or are there bypasses?*
  (Search for direct `requests.`/`httpx.`/`open(`/`socket.` calls outside the seam —
  bypasses are a code smell and a testing hazard; note them.)

State the seam by file and symbol. The entire pyramid is organized around it: Layer 1
mocks *above* it, Layer 2 exercises the seam itself mocked at the network/disk edge,
Layer 3 runs the whole process against a fake on the other side of it.

### 1.3 Map the secondary seams

Every source of nondeterminism or environmental coupling is a seam you must control:

- **Config loading** — where config is parsed; can you point it at fixtures?
- **Subprocess spawning** — what gets spawned, with what env?
- **Clock / time** — `now()`, sleeps, timeouts, retries with backoff.
- **Randomness** — UUIDs, random ports, jitter.
- **Filesystem** — temp dirs, caches, log files, generated artifacts.
- **Environment variables** — what the code reads and how it's validated.

For each, note *how* you'll control it in tests (dependency injection, monkeypatch,
`tmp_path`, fixed seed, fake clock).

### 1.4 Identify the async/sync boundary

This is a correctness trap, not a detail. Determine precisely:
- Which layer is async and which is sync (e.g. "the client and registration are async;
  the tool functions themselves are sync and wrapped by a decorator").
- What the test framework needs to drive async code (`pytest-asyncio` mode, an event
  loop fixture, `asyncio.run`, etc.).
- Where an `await` is missing-but-silent vs. where it would crash.

A test suite that gets this boundary wrong produces tests that pass without ever
executing the code under test. Get it right and write it down.

### 1.5 Document the current testing gap

Write the honest before-state:
- **What is tested now** (could be "nothing" or "manual only").
- **What breaks silently on a bad push today** — be specific: "renaming an action in a
  config file points it at a non-existent handler and nothing catches it until a human
  notices in production."
- **What manual process this strategy replaces**, and what that costs (human minutes per
  change, reproducibility, quality of failure signal).

### Questions to ask yourself in Phase 1

- What is the *one* thing every external call passes through?
- What would a reviewer never notice in a diff but that would break a user?
- Which config/data files change behavior with zero code change? (Those need their own
  tests — edits to them are invisible to code-focused review.)
- Where does the process actually assemble itself, and could I run that assembly in a
  subprocess against a fake backend?
- What's nondeterministic, and how do I pin it?

---

## Phase 2 — Design the Test Pyramid

Define **3 to 5 layers**. Layers 1 and 2 are mandatory; Layer 3 is mandatory for any
system with a process/assembly boundary; Layers 4 and 5 are conditional. Each layer must
answer a **different question** and catch something **no other layer catches**. If a
layer doesn't earn its place by that test, cut it.

### The canonical layers

**Layer 1 — Unit (always).**
- Tests functions/classes in-process with the **primary seam mocked**.
- No network, no disk I/O, no subprocess. Pure logic.
- Catches: routing bugs, parameter construction, state machines (e.g. a confirmation
  handshake), config parsing, branching logic.
- Fastest feedback — should run in single-digit seconds.

**Layer 2 — Integration (always).**
- Tests the **primary seam itself** — the real client/driver/wrapper — mocked only at
  the outermost network/disk edge.
- Tooling by domain: `respx`/`responses`/`httpretty`/VCR for HTTP; in-memory SQLite or a
  transactional fixture for databases; `tmp_path` for filesystem; an embedded broker for
  queues.
- Catches: bugs that only appear once the real request/query/command is *built* — URL
  assembly, auth headers, retry/backoff counts, timeout handling, serialization, double
  slashes, encoding.

**Layer 3 — Functional / Component (whenever there's an assembly boundary).**
- Tests the **assembled system as a process** (subprocess or in-process app boundary),
  talking to a **stub/fake backend** on the far side of the primary seam. The code
  "thinks" it's talking to real infrastructure.
- This layer is usually the **centerpiece** — it's what replaces manual end-to-end
  checking with deterministic tests. Sub-divide it as the project warrants, e.g.:
  - *3a* — wiring/registration (the right things are exposed/configured),
  - *3b* — **workflow tests** (multi-step user journeys, each step verified at the wire
    via the stub's request recorder — this is what retires the manual playbook),
  - *3c* — cross-cutting protocol behavior (e.g. a confirmation/handshake/auth flow over
    the real transport).
- Catches: a config edit that silently changes what's exposed; a renamed handler the
  config still points at; a regression in a safety mechanism — with a *precise* failure
  message ("endpoint X was never called") instead of "it didn't work."

**Layer 4 — E2E against real infrastructure (optional, advisory).**
- Same assembled system, pointed at a **real external instance**, run on demand.
- Catches: real contract drift, real auth, real latency, license/permission tiers.
- **Advisory only** — never a merge gate (too slow, too flaky, needs secrets/infra).

**Layer 5 — AI/LLM-driven (only if the project has an AI or natural-language surface).**
- Drives the system from **plain-English tasks** to test discoverability and usability:
  given only a task and the tool/command schemas, can the agent find and correctly use
  the right capability — and did the operation **actually take effect**?
- Catches: confusing names, vague descriptions, undiscoverable capabilities, broken
  async UX. These are *product* findings no scripted test can surface.
- **Advisory only.** If the project has no AI/NL surface, omit this layer entirely.

### Specify each layer in a table

For every layer you keep, fill in:

| Field | Must state |
|---|---|
| Question it answers | One sentence |
| Catches what nothing else does | The unique failure mode |
| Infrastructure needed | Fixtures, stubs, mocks, fakes |
| Blocks merge? | Yes (gate) / No (advisory) |
| Needs real infra? | Yes/No |
| Estimated runtime | Order of magnitude |

End Phase 2 with the pyramid diagram (ASCII box stack) showing the layers, what each
talks to, and test count/runtime placeholders — you'll fill counts in after Phase 4.

---

## Phase 3 — Infrastructure Design

Design the machinery the layers need. Be concrete and name components.

### 3.1 Parametrization strategy

You will have many similar cases (every action, every config rule, every persona/role).
**Do not write one test function per case.** Design a parametrization engine that reads
the project's own config/spec/data files and generates cases:

- Parse the config files (the same `.txt`/`.yaml`/`.json` that drive the app) into a list
  of cases.
- Feed them to the test framework's parametrize mechanism so each case is an individually
  reported test that you never hand-wrote.
- The payoff: when someone adds a row to a config file, a new test case appears
  automatically and is covered for free.

Name this component (e.g. `config_cases.py`) and describe what it parses and emits.

### 3.2 Stub / fake backend (for Layer 3)

Design the fake that sits on the far side of the primary seam:

- A tiny in-process server/fake (e.g. a minimal Starlette/Flask app for HTTP; an
  in-memory store for a DB; a fake broker).
- It must **record every request/call** so tests can assert *exactly* what the system
  sent — the recorder is what gives precise failure messages.
- It returns **canned, shape-appropriate responses**. Provide explicit handlers for the
  core paths and a **catch-all** for the long tail.
- Decide deliberately what it should *not* serve, to force known fallback behavior
  (document the reasoning).
- It runs on a **random free port** inside the test process; the assembled system is
  pointed at it via env/config.

Name it (e.g. `dct_stub`) and sketch the request/response data flow as a diagram.

### 3.3 Test CLI runner (if the project warrants one)

If the project benefits from a single entry point for all test layers, design a CLI:

```
<project>-test --layer <unit|integration|functional|ci|e2e|...>
```

- One runner, callable from a terminal, from CI, and (if applicable) from inside an
  agent/IDE skill.
- `--layer ci` = the offline gate (Layers 1–3). Other flags select individual layers or
  real-infra layers.
- Add domain-specific flags as needed (e.g. `--persona`, `--report results.xml`,
  `--base-url`, `--api-key`).

### 3.4 Fixture hierarchy

Define the layering of fixtures:
- **Shared** (top-level `conftest`) — the stub, the parametrization data, env setup.
- **Layer-specific** (per-layer `conftest`) — transport builders (in-process vs.
  subprocess vs. real), credential injection.
- **Module-specific** — per-resource fixtures.

State where the single source of truth for "how to launch the real system" lives (e.g. a
`.mcp.json` / a compose file / a connection string) and that both the E2E and any AI
layer read from it rather than duplicating launch config.

---

## Phase 4 — Coverage Target and Honest Gap Analysis

### 4.1 Set a realistic target per layer

- State a target for the offline gate (e.g. "L1+L2+L3 combined ≥ 90%").
- **100% is explicitly not the goal.** Justify the target you pick.

### 4.2 Run coverage, then categorize *every* missed line

After implementation, run coverage and put **each missed line into exactly one** of
these buckets, with the file:line and a one-line reason:

| Bucket | Meaning | Right response |
|---|---|---|
| **Unreachable in dev/test mode** | `if 'site-packages' in __file__`, `if __name__ == "__main__"`, install-only branches | Leave uncovered; don't mock `__file__` |
| **Catastrophic infra failure** | Framework crash at startup, disk full, OS-level error handlers | Leave uncovered; fault injection isn't worth the brittleness |
| **Live-system-only paths** | Requires a real external service (runtime spec download, live auth) | Covered by Layer 4/5, not the offline gate |
| **Dead / obsolete code** | Stubs, `pass`, no-ops, unreachable branches | Delete the code, or note it |
| **Genuinely missing test** | A real path with no excuse | Write the test |

The discipline: **if a missed line has no reason, it needs a test.** Every other missed
line gets a sentence.

### 4.3 State the coverage policy explicitly

In the docs, write the policy in plain language. The load-bearing sentence:

> **X% with documented gaps is better than Y% via brittle mocks.** Mocking the boundary
> you're supposed to be testing — `__file__`, the clock, framework internals — produces
> tests that test the mocks, not the code. Gaps are documented, not hidden.

---

## Phase 5 — CI/CD Wiring

- **Merge gate workflow** (GitHub Actions or equivalent): on every push/PR, run the
  offline layers via the CLI (`<project>-test --layer ci`). Use a **non-editable
  install** if the project generates artifacts into the source tree in dev mode (so
  generation goes to a temp dir, matching production). State this if it applies.
- **On-demand real-infra workflow**: `workflow_dispatch` (manual trigger), pulling
  credentials from CI secrets; optionally a nightly `schedule`.
- **Secrets strategy**: name the secrets (e.g. `BASE_URL`, `API_KEY`), state they come
  from CI secret storage and are never hardcoded or committed.
- **Branch protection**: note that making the gate a *required check* is the step that
  actually prevents red merges, and that it's an admin/process action distinct from
  writing the workflow file. Don't claim it's enforced if it isn't — list it as pending.

---

## Phase 6 — Documentation Output

Produce **both** documents. They must agree on every number and claim.

### 6.1 `test-strategy.md`

A markdown design doc with these sections (adapt headings to the project, keep the
substance):

1. **Problem Statement** — what's broken about testing today, what this replaces.
2. **Summary table** — every layer: what it proves, what it uniquely catches, needs real
   infra?, trigger, blocks merge? Plus a before/after table.
3. **Core Insight — the two questions** — the regression-gate vs. usability/contract
   split, as a table.
4. **Current State (baseline)** — what existed, what didn't, and the **test seams already
   present in the code** (this is where Phase 1.2/1.3 pays off).
5. **Architecture** — the pyramid diagram + per-layer prose, including how the real-infra
   layers find their launch config.
6. **The centerpiece layer (3b)** — the workflow-test pattern, with a real code example
   and a mapping table from manual scenarios → workflow tests.
7. **The stub component** — data-flow diagram, routes, what it deliberately doesn't serve.
8. **AI/LLM testing** (if applicable) — driver, the act→verify pattern, verification
   tiers, real findings.
9. **Infrastructure / Changes Made** — every file created, by role.
10. **When Tests Run** — trigger → what runs → invocation → blocking? table.
11. **Coverage Analysis** — target, per-module table, the bucketed gap analysis, the
    policy statement.
12. **Roadmap** — completed vs. in-progress vs. future.
13. **Success Criteria** — checklists per layer.
14. **Out of Scope** — what you deliberately don't test (load/perf, exhaustive E2E, etc.).

### 6.2 `test-strategy.html`

A self-contained, dark-themed, **tabbed** HTML page — each major section is a clickable
tab. Match the reference styling exactly. Use these CSS variables verbatim:

```css
:root {
  --bg:#0f1419; --panel:#1a2028; --panel-2:#232b35; --border:#2d3742;
  --text:#d5dde6; --muted:#8a96a3; --accent:#4fc3f7; --accent-2:#81d4fa;
  --good:#66bb6a; --warn:#ffa726; --bad:#ef5350; --code-bg:#0a0e13; --code-text:#c8d4e0;
  --star:#ffd54f;
}
```

Required structural/style elements (carry over from the reference):

- A `<header>` with a gradient background, an `<h1>`, and a `.sub` line carrying
  branch / test-count / date.
- A sticky `<nav>` of `<button>` tabs; the active tab uses `--accent` with a bottom
  border; clicking calls a `show(id, btn)` JS function that toggles `.active` on the
  matching `<section>`.
- Each section is a `<section>` with `display:none` until `.active`, with a short
  `fadeIn` animation.
- **Cards** with left-border accent variants: `.card-good` (green), `.card-warn`
  (amber), `.card-bad` (red), `.card-accent` (blue), and a `.card-star` (highlight the
  centerpiece layer).
- **Stat grid** (`.stat-grid` / `.stat` / `.stat-value` / `.stat-label`) for the
  headline numbers (test count, coverage %, runtime, etc.).
- **Tag pills** (`.tag` with per-layer color classes `t-unit`/`t-int`/`t-func`/`t-e2e`/
  `t-llm` and status `t-good`/`t-warn`/`t-bad`/`t-star`).
- **Split panels** (`.split` two-column grid) for the two-questions framing, each ending
  in a `.split-q` callout containing the literal question in quotes.
- **Flow diagrams** (`.flow-diagram`, monospace, `white-space:pre`) for the pyramid and
  the stub data flow.
- **Checklists** (`.checklist` with a green ✓ pseudo-element) and **cross-lists**
  (`.crosslist` with a red ✕) for what exists / doesn't.
- `.done-badge` / `.future-badge` inline status badges.
- Self-contained: all CSS in a `<style>` block, the `show()` function in a trailing
  `<script>`. No external assets, no frameworks.

The minimal JS pattern:

```javascript
function show(id, btn) {
  document.querySelectorAll('section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  if (btn) btn.classList.add('active');
}
```

---

## Non-negotiable principles (apply throughout)

These are the things that separate this from a generic test plan. Bake each one into the
strategy and call it out in the docs.

### The act → verify principle (mandatory for every mutation test)

> **Never trust the same call that performed the action to confirm it. Always read the
> state back independently.**

- After any create/update/delete, **re-read** the state through a separate call/query and
  assert the change is real.
- For async operations, **wait for the job/task to reach a terminal state** before
  verifying — never declare success on submission alone.
- For AI-driven tests specifically: the verify step must be a **separate** invocation,
  and **the identifier being confirmed must not appear in the verify prompt** — otherwise
  the model will echo it back regardless of real state. This is a real false-pass trap;
  name it in the docs.

### Test failure modes, not lines

State, in the docs, the named failure modes you set out to catch — e.g.:
- "A config edit repoints an action at a handler that no longer exists."
- "A safety/confirmation gate stops gating a destructive op."
- "The retry count silently changes."
- "The auth header format regresses."
- "A capability becomes undiscoverable from natural language."

The pyramid exists to catch *these*, cheaply, at the lowest possible layer. Coverage % is
the diagnostic that tells you whether you missed one.

### Precise failure messages over green/red

A failing test must say *what specifically broke* ("POST /resource/start was never
called"), not "it didn't work." The stub's request recorder is what buys you this; design
for it.

### Be specific, never generic

Don't write "use good mocks" — name the tool (`respx`), the seam (`Client.make_request`),
the fixture (`tmp_path`), the tradeoff ("mocking `__file__` is worse than a 3-line gap").
Every claim in the docs should be checkable against the code.

---

## Deliverables checklist

By the end you must have produced:

- [ ] **Phase 1 written analysis** — primary seam (file:symbol), secondary seams, the
      async/sync boundary, and the documented current gap.
- [ ] **The parametrization engine** — reads the project's own config/spec files, emits
      one test case per row.
- [ ] **The stub / fake backend** — records requests, canned responses, catch-all,
      random port, named.
- [ ] **Test files for every layer kept** — L1 unit, L2 integration, L3 functional
      (sub-divided), L4 e2e (if applicable), L5 AI (if applicable).
- [ ] **The test CLI runner** (if warranted) — `<project>-test --layer …`.
- [ ] **CI workflows** — the offline merge-gate workflow and the on-demand real-infra
      workflow.
- [ ] **Coverage report + bucketed gap analysis** — every missed line categorized with a
      reason; the policy statement written.
- [ ] **`test-strategy.md`** — all sections from Phase 6.1.
- [ ] **`test-strategy.html`** — dark tabbed UI, exact CSS variables, all sections as
      tabs, self-contained.

Begin with Phase 1. Read the code first. Do not write a single test or document section
until you can name the primary seam and the failure modes you intend to catch.
