#!/usr/bin/env bash
# manage-state.sh — Track step completion state for feature-implement workflows
#
# Usage:
#   .claude/evals/manage-state.sh <NAME> --init --domain <domain> [--lite_mode true|false] [--domain_source <src>] [--skip_phases <csv>] [--force]
#   .claude/evals/manage-state.sh <NAME> --check
#   .claude/evals/manage-state.sh <NAME> --status
#   .claude/evals/manage-state.sh <NAME> --step-status <step>
#   .claude/evals/manage-state.sh <NAME> --complete <step> [--pr-url <url>]
#   .claude/evals/manage-state.sh <NAME> --skip <step>
#   .claude/evals/manage-state.sh <NAME> --reset
#   .claude/evals/manage-state.sh <NAME> --get-skip-phases
#   .claude/evals/manage-state.sh <NAME> --get-pr-url
#   .claude/evals/manage-state.sh <NAME> --list-phases
#
# Exit conventions (--check):
#   exit 0 = no state file found (fresh run)
#   exit 1 = state file found (resume) — note: inverted from POSIX success convention

set -euo pipefail

# Single source of truth for the canonical step order.
# Any VALID_STEPS= assignment in this script must use this variable.
# Python literals inside heredocs cannot reference bash vars — each is annotated
# with "# Must match $CANONICAL_STEPS above".
CANONICAL_STEPS="context vision design implement build test-infra test validate pr release retrospective"

_script_dir=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || _script_dir=$(dirname "$0")
SCRIPT_PATH="${_script_dir}/$(basename "$0")"

NAME="${1:-}"
ACTION="${2:-}"

if [[ -z "$NAME" || -z "$ACTION" ]]; then
  echo "Usage: $0 <NAME> --init --domain <domain> [--lite_mode true|false] [--domain_source <src>] [--skip_phases <csv>] [--force] | --check | --status | --next-step | --step-status <step> | --complete <step> [--pr-url <url>] | --skip <step> | --reset | --get-skip-phases | --get-pr-url | --list-phases"
  exit 1
fi
if [[ "$NAME" == -* ]]; then
  echo "ERROR: NAME must not start with '-'"
  exit 1
fi
if [[ ! "$NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo "ERROR: invalid NAME — must be alphanumeric with hyphens/underscores only"
  exit 1
fi

STATE_FILE=".claude/${NAME}-state.json"

# Validate JSON + schema_version; prints error and exits 2 if corrupt/unknown schema.
# Also backfills missing 'skipped_phases' key (backwards compatibility for old state files).
# Used by actions that read state so corrupt files are caught early, not just in --check.
_validate_state() {
  if ! python3 - "$STATE_FILE" <<'PYEOF'
import json, sys, os
SUPPORTED_SCHEMAS = {1}
REQUIRED_KEYS = {'schema_version', 'name', 'domain', 'steps', 'next_step'}
state_file = sys.argv[1]
try:
    state = json.load(open(state_file))
except Exception:
    print(f"ERROR: state file is not valid JSON", file=sys.stderr)
    sys.exit(1)
v = state.get('schema_version')
if v not in SUPPORTED_SCHEMAS:
    print(f"ERROR: schema_version {v!r} not supported — run --reset to start fresh", file=sys.stderr)
    sys.exit(1)
missing = REQUIRED_KEYS - set(state.keys())
if missing:
    print(f"ERROR: state file missing required keys: {sorted(missing)}", file=sys.stderr)
    sys.exit(1)
if not isinstance(state['steps'], dict):
    print("ERROR: state file 'steps' must be a dict", file=sys.stderr)
    sys.exit(1)
# Must match $CANONICAL_STEPS above
CANONICAL_STEPS = ['context','vision','design','implement','build','test-infra','test','validate','pr','release','retrospective']
missing_steps = [s for s in CANONICAL_STEPS if s not in state['steps']]
if missing_steps:
    print(f"ERROR: state file 'steps' missing canonical keys: {missing_steps}", file=sys.stderr)
    sys.exit(1)
# Backwards compatibility: skipped_phases key may be absent in old state files (read-only check; callers that write will add it)
if 'skipped_phases' not in state:
    pass  # callers that mutate state will add this key before writing
PYEOF
  then
    echo "ERROR: state file '$STATE_FILE' is corrupt or has an unsupported schema — run '.claude/evals/manage-state.sh $NAME --reset' to start fresh"
    exit 2
  fi
}

case "$ACTION" in
  --init)
    DOMAIN="feature"
    LITE_MODE_VAL="false"
    DOMAIN_SOURCE_VAL=""
    SKIP_PHASES_VAL=""
    FORCE_FLAG=false
    i=3
    while [[ $i -le $# ]]; do
      case "${!i}" in
        --domain)
          i=$((i+1))
          if [[ $i -gt $# ]]; then echo "ERROR: --domain requires a value"; exit 1; fi
          if [[ "${!i}" == -* ]]; then echo "ERROR: --domain value cannot start with '-' (got: '${!i}')"; exit 1; fi
          DOMAIN="${!i}" ;;
        --lite_mode)
          i=$((i+1))
          if [[ $i -gt $# ]]; then echo "ERROR: --lite_mode requires a value (true|false)"; exit 1; fi
          if [[ "${!i}" == -* ]]; then echo "ERROR: --lite_mode value cannot start with '-' (got: '${!i}')"; exit 1; fi
          LITE_MODE_VAL="${!i}" ;;
        --domain_source)
          i=$((i+1))
          if [[ $i -gt $# ]]; then echo "ERROR: --domain_source requires a value"; exit 1; fi
          if [[ "${!i}" == -* ]]; then echo "ERROR: --domain_source value cannot start with '-' (got: '${!i}')"; exit 1; fi
          DOMAIN_SOURCE_VAL="${!i}" ;;
        --skip_phases)
          i=$((i+1))
          if [[ $i -gt $# ]]; then echo "ERROR: --skip_phases requires a value (csv or empty string)"; exit 1; fi
          if [[ "${!i}" == -* ]]; then echo "ERROR: --skip_phases value cannot start with '-' (got: '${!i}')"; exit 1; fi
          SKIP_PHASES_VAL="${!i}" ;;
        --force)        FORCE_FLAG=true ;;
        --*)            echo "ERROR: unknown flag '${!i}'"; exit 1 ;;
      esac
      i=$((i+1))
    done
    if [[ -z "$DOMAIN" ]]; then
      echo "ERROR: --domain requires a value"
      exit 1
    fi
    if [[ "$LITE_MODE_VAL" != "true" && "$LITE_MODE_VAL" != "false" ]]; then
      echo "ERROR: invalid --lite_mode value '$LITE_MODE_VAL' — must be 'true' or 'false'"
      exit 1
    fi
    # NAME alnum check already applied at top of script (before STATE_FILE construction)
    if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9_-]+$ ]]; then
      echo "ERROR: invalid DOMAIN — must be alphanumeric with hyphens/underscores only"
      exit 1
    fi
    mkdir -p .claude  # after validation: NAME and DOMAIN are safe to use in path
    if [[ -f "$STATE_FILE" ]]; then
      # Require --force to avoid silently discarding a previous workflow run
      if [[ "$FORCE_FLAG" != "true" ]]; then
        echo "ERROR: state file '$STATE_FILE' already exists — pass --force to overwrite and discard prior progress"
        exit 1
      fi
      echo "WARNING: overwriting existing state for '${NAME}' — prior progress will be lost"
    fi
    # A prior run may have left docs/$NAME/.conflict-retest-count behind (persisted
    # deliberately across resumes so the pr-phase conflict-retest cap holds — see
    # feature-implement SKILL.md Step 5). --init always means "(re)start tracking
    # this NAME from scratch", so a stale count must not carry over and falsely
    # trip the max-attempts halt on a run that hasn't made any real attempts yet.
    rm -f "docs/${NAME}/.conflict-retest-count"
    # Same reasoning applies to docs/$NAME/.review-comment-retest-count, the
    # sibling counter the review-comment-resolver skill persists for its own
    # 3-attempt build-retest cap (SKILL.md Step 7a) — it must not survive an
    # explicit --init either.
    rm -f "docs/${NAME}/.review-comment-retest-count"
    python3 - "$NAME" "$DOMAIN" "$LITE_MODE_VAL" "$DOMAIN_SOURCE_VAL" "$STATE_FILE" "$SKIP_PHASES_VAL" <<'PYEOF'
import json, sys, os
from datetime import datetime, timezone
name, domain, lite_mode, domain_source, state_file, skip_phases_csv = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
# Must match $CANONICAL_STEPS above
steps = ['context','vision','design','implement','build','test-infra','test','validate','pr','release','retrospective']
# Parse, validate, and apply skip_phases CSV
raw_phases = [p.strip() for p in skip_phases_csv.split(',') if p.strip()] if skip_phases_csv.strip() else []
invalid = [p for p in raw_phases if p not in steps]
if invalid:
    print(f"ERROR: --skip_phases contains unknown phase(s): {invalid}. Valid: {steps}", file=sys.stderr)
    sys.exit(1)
if 'context' in raw_phases:
    print("ERROR: 'context' cannot be skipped — it bootstraps eval scripts required by all other phases", file=sys.stderr)
    sys.exit(1)
skipped_phases = raw_phases
steps_state = {s: ('skipped' if s in skipped_phases else 'pending') for s in steps}
# next_step: first non-skipped, non-completed step
next_step = next((s for s in steps if steps_state[s] == 'pending'), '')
state = {
    'schema_version': 1,
    'name': name,
    'domain': domain,
    'lite_mode': lite_mode == 'true',
    'domain_source': domain_source,
    'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'steps': steps_state,
    'last_completed': '',
    'next_step': next_step or 'context',
    'skipped_phases': skipped_phases,
    'pr_url': ''
}
tmp_path = state_file + '.tmp'
with open(tmp_path, 'w') as f:
    json.dump(state, f, indent=2)
os.replace(tmp_path, state_file)
print(f'State initialized for {name} (domain: {domain}, lite_mode: {lite_mode}, schema_version: 1, skipped_phases: {", ".join(skipped_phases) if skipped_phases else "none"})')
PYEOF
    ;;

  --check)
    if [[ ! -f "$STATE_FILE" ]]; then
      exit 0  # No state — signal fresh run
    fi
    # Validate JSON and schema_version before treating as valid resume state (exit 2 = corrupt/unknown schema)
    if ! python3 - "$STATE_FILE" 2>/dev/null <<'PYEOF'
import json, sys
SUPPORTED_SCHEMAS = {1}
try:
    state = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
v = state.get('schema_version')
if v not in SUPPORTED_SCHEMAS:
    print(f"ERROR: schema_version {v!r} not supported — run --reset to start fresh", file=sys.stderr)
    sys.exit(1)
PYEOF
    then
      echo "ERROR: state file '$STATE_FILE' is corrupt or has an unsupported schema — run '.claude/evals/manage-state.sh $NAME --reset' to start fresh"
      exit 2
    fi
    # State exists and is valid — print status table and exit 1 to signal resume
    bash "$SCRIPT_PATH" "$NAME" --status
    exit 1
    ;;

  --step-status)
    # Returns the status of a specific step: prints "pending" or "completed", exits 0 for completed, 1 for pending/unknown.
    STEP="${3:-}"
    if [[ -z "$STEP" ]]; then
      echo "Usage: $0 <NAME> --step-status <step>"
      exit 1
    fi
    VALID_STEPS="$CANONICAL_STEPS"
    if [[ "$STEP" == *" "* ]] || ! echo "$VALID_STEPS" | grep -qwF "$STEP"; then
      echo "ERROR: unknown step '$STEP'"
      exit 1
    fi
    if [[ ! -f "$STATE_FILE" ]]; then
      echo "pending"
      exit 1
    fi
    _validate_state
    python3 - "$STEP" "$STATE_FILE" <<'PYEOF'
import json, sys
step, state_file = sys.argv[1], sys.argv[2]
with open(state_file) as f:
    state = json.load(f)
status = state.get('steps', {}).get(step, 'pending')
print(status)
sys.exit(0 if status in ('completed', 'skipped') else 1)
PYEOF
    ;;

  --status)
    if [[ ! -f "$STATE_FILE" ]]; then
      echo "No state file found for ${NAME}"
      exit 0
    fi
    _validate_state
    python3 - "$STATE_FILE" <<'PYEOF'
import json, sys
state_file = sys.argv[1]
with open(state_file) as f:
    state = json.load(f)
created = state.get('created_at', '')[:10]
is_lite = state.get('lite_mode', False)
lite_phases = {'context', 'implement', 'pr'}
print(f"{state['name']} ({state['domain']}) — started {created}")
# Must match $CANONICAL_STEPS above
ordered = ['context','vision','design','implement','build','test-infra','test','validate','pr','release','retrospective']
# Warn if skipped_phases list and steps dict disagree (can happen after manual edits)
skipped_phases_list = set(state.get('skipped_phases', []))
skipped_in_steps = {s for s, v in state.get('steps', {}).items() if v == 'skipped'}
mismatch = skipped_phases_list.symmetric_difference(skipped_in_steps)
if mismatch:
    print(f"WARNING: skipped_phases list and steps dict disagree for: {sorted(mismatch)} — state may have been edited manually. Run --reset to start fresh if behavior is unexpected.", file=sys.stderr)
next_step = state.get('next_step', '')
for s in ordered:
    if is_lite and s not in lite_phases:
        print(f'  ▭ {s:<24} skipped (lite)')
        continue
    status = state['steps'].get(s, 'pending')
    if status == 'skipped':
        print(f'  ▷ {s:<24} skipped')
        continue
    marker = '\u2713' if status == 'completed' else '\u25cb'
    arrow = '    \u2190 next' if s == next_step else ''
    print(f'  {marker} {s:<24} {status}{arrow}')
PYEOF
    ;;

  --complete)
    STEP="${3:-}"
    if [[ -z "$STEP" ]]; then
      echo "Usage: $0 <NAME> --complete <step> [--pr-url <url>]"
      exit 1
    fi
    VALID_STEPS="$CANONICAL_STEPS"
    if [[ "$STEP" == *" "* ]] || ! echo "$VALID_STEPS" | grep -qwF "$STEP"; then
      echo "ERROR: unknown step '$STEP'"
      exit 1
    fi
    # Optional --pr-url <url> (typically passed with `--complete pr`). Persisted to the
    # pr_url field so the pipeline-mode completion result.json carries a non-null PR URL.
    PR_URL_VAL=""
    i=4
    while [[ $i -le $# ]]; do
      case "${!i}" in
        --pr-url)
          i=$((i+1))
          if [[ $i -gt $# ]]; then echo "ERROR: --pr-url requires a value"; exit 1; fi
          PR_URL_VAL="${!i}" ;;
        --*) echo "ERROR: unknown flag '${!i}'"; exit 1 ;;
      esac
      i=$((i+1))
    done
    if [[ ! -f "$STATE_FILE" ]]; then
      echo "WARNING: No state file found for ${NAME} — skipping --complete"
      exit 0
    fi
    _validate_state
    python3 - "$STEP" "$STATE_FILE" "$PR_URL_VAL" <<'PYEOF'
import json, sys, os
step, state_file = sys.argv[1], sys.argv[2]
pr_url = sys.argv[3] if len(sys.argv) > 3 else ''
# Must match $CANONICAL_STEPS above
ordered = ['context','vision','design','implement','build','test-infra','test','validate','pr','release','retrospective']
lite_phases = {'context', 'implement', 'pr'}
with open(state_file) as f:
    state = json.load(f)
# Idempotent: if already completed, note it and fall through to recompute/persist next_step
already_done = state['steps'].get(step) == 'completed'
if already_done:
    print(f'Note: {step} was already completed — idempotent re-mark (recomputing next_step)')
# Reject out-of-order completion; 'skipped' phases are not pending blockers (skipped != pending)
is_lite = state.get('lite_mode', False)
step_idx = ordered.index(step)
if is_lite:
    pending_before = [s for s in ordered[:step_idx] if s in lite_phases and state['steps'].get(s) == 'pending']
else:
    pending_before = [s for s in ordered[:step_idx] if state['steps'].get(s) == 'pending']
if not already_done and pending_before:
    print(f'ERROR: completing {step} out of order — still pending: {", ".join(pending_before)}', file=sys.stderr)
    sys.exit(1)
if not already_done:
    state['steps'][step] = 'completed'
    state['last_completed'] = step
# Persist the PR URL when provided (backfill key for old state files). Only overwrite
# with a non-empty value so an idempotent re-mark without --pr-url never clears it.
if 'pr_url' not in state:
    state['pr_url'] = ''
if pr_url:
    state['pr_url'] = pr_url
# In lite mode only surface the next non-skipped (lite) phase as next_step
next_step = ''
for s in ordered:
    if state['steps'].get(s) == 'pending':
        if not is_lite or s in lite_phases:
            next_step = s
            break
state['next_step'] = next_step
tmp_path = state_file + '.tmp'
with open(tmp_path, 'w') as f:
    json.dump(state, f, indent=2)
os.replace(tmp_path, state_file)
label = next_step if next_step else '(all done)'
print(f'Marked {step} as completed. Next step: {label}')
PYEOF
    ;;

  --skip)
    STEP="${3:-}"
    if [[ -z "$STEP" ]]; then
      echo "Usage: $0 <NAME> --skip <step>"
      exit 1
    fi
    VALID_STEPS="$CANONICAL_STEPS"
    if [[ "$STEP" == *" "* ]] || ! echo "$VALID_STEPS" | grep -qwF "$STEP"; then
      echo "ERROR: unknown step '$STEP'"
      exit 1
    fi
    if [[ "$STEP" == "context" ]]; then
      echo "ERROR: context cannot be skipped — it bootstraps eval scripts required by all other phases"
      exit 1
    fi
    if [[ ! -f "$STATE_FILE" ]]; then
      echo "WARNING: No state file found for ${NAME} — skipping --skip"
      exit 0
    fi
    _validate_state
    python3 - "$STEP" "$STATE_FILE" <<'PYEOF'
import json, sys, os
step, state_file = sys.argv[1], sys.argv[2]
# Must match $CANONICAL_STEPS above
ordered = ['context','vision','design','implement','build','test-infra','test','validate','pr','release','retrospective']
lite_phases = {'context', 'implement', 'pr'}
with open(state_file) as f:
    state = json.load(f)
# Advisory: if lite mode is active, this phase is already excluded — redundant --skip
is_lite = state.get('lite_mode', False)
lite_phases = {'context', 'implement', 'pr'}
if is_lite and step not in lite_phases:
    print(f'Note: {step} is already excluded in lite mode — --skip is redundant (no-op). Recording as skipped anyway for state clarity.')
current_status = state.get('steps', {}).get(step, 'pending')
if current_status == 'completed':
    print(f'ERROR: {step} is already completed — cannot mark as skipped', file=sys.stderr)
    sys.exit(1)
already_skipped = current_status == 'skipped'
if already_skipped:
    print(f'Note: {step} was already skipped — idempotent re-mark (recomputing next_step)')
else:
    state['steps'][step] = 'skipped'
    # Also append to skipped_phases list if not already present
    if 'skipped_phases' not in state:
        state['skipped_phases'] = []
    if step not in state['skipped_phases']:
        state['skipped_phases'].append(step)
# Do not update last_completed — skipped phases are not "done" in the completion sense
# Recompute next_step: next step that is still pending (not completed, not skipped)
is_lite = state.get('lite_mode', False)
next_step = ''
for s in ordered:
    if state['steps'].get(s) == 'pending':
        if not is_lite or s in lite_phases:
            next_step = s
            break
state['next_step'] = next_step
tmp_path = state_file + '.tmp'
with open(tmp_path, 'w') as f:
    json.dump(state, f, indent=2)
os.replace(tmp_path, state_file)
label = next_step if next_step else '(all done)'
print(f'Marked {step} as skipped. Next step: {label}')
PYEOF
    ;;

  --next-step)
    # Prints the next pending step name (machine-parseable). Exits 0 if a step is pending, 1 if all done.
    if [[ ! -f "$STATE_FILE" ]]; then
      echo "context"
      exit 0
    fi
    _validate_state
    python3 - "$STATE_FILE" <<'PYEOF'
import json, sys
state_file = sys.argv[1]
with open(state_file) as f:
    state = json.load(f)
next_step = state.get('next_step', '')
if next_step:
    print(next_step)
    sys.exit(0)
else:
    print('(all done)')
    sys.exit(1)
PYEOF
    ;;

  --reset)
    # See --init above: docs/$NAME/.conflict-retest-count is persisted deliberately
    # across resumes but must not survive an explicit reset.
    rm -f "docs/${NAME}/.conflict-retest-count"
    rm -f "docs/${NAME}/.review-comment-retest-count"
    if [[ -f "$STATE_FILE" ]]; then
      rm "$STATE_FILE"
      rm -f "${STATE_FILE}.tmp"
      echo "State reset for ${NAME}"
    else
      rm -f "${STATE_FILE}.tmp"
      echo "No state file to reset for ${NAME}"
    fi
    # init_facts (runtime/lib.sh) is a no-op if docs/$NAME/$NAME-facts.json already
    # exists, by design — it must not clobber decisions[]/scope/branch/worktree_path
    # that later phases accumulated during a normal resume. But that guard means an
    # explicit --reset, on its own, would leave stale ticket-derived facts
    # (title/ACs/constraints) in place: the next bootstrap run re-fetches the ticket
    # from Jira, but init_facts sees the old facts.json and silently keeps the old
    # values, defeating the point of resetting after the ticket changed upstream.
    # --reset is the explicit "start fresh" signal, so remove facts.json here too —
    # the next run's init_facts call then regenerates it from the current ticket.
    if [[ -f "docs/${NAME}/${NAME}-facts.json" ]]; then
      rm -f "docs/${NAME}/${NAME}-facts.json"
      echo "Removed docs/${NAME}/${NAME}-facts.json — the next run will re-derive it from the current ticket/description."
    fi
    ;;

  --get-skip-phases)
    # Prints the skipped_phases array as a comma-joined string, or empty string if none.
    # Always exits 0.
    if [[ ! -f "$STATE_FILE" ]]; then
      echo ""
      exit 0
    fi
    _validate_state
    python3 - "$STATE_FILE" <<'PYEOF'
import json, sys
state_file = sys.argv[1]
with open(state_file) as f:
    state = json.load(f)
phases = state.get('skipped_phases', [])
print(','.join(phases))
sys.exit(0)
PYEOF
    ;;

  --get-pr-url)
    # Prints the persisted PR/change URL, or empty string if none. Always exits 0.
    if [[ ! -f "$STATE_FILE" ]]; then
      echo ""
      exit 0
    fi
    _validate_state
    python3 - "$STATE_FILE" <<'PYEOF'
import json, sys
state_file = sys.argv[1]
with open(state_file) as f:
    state = json.load(f)
print(state.get('pr_url', ''))
sys.exit(0)
PYEOF
    ;;

  --list-phases)
    # Prints the canonical step list, one step per line. Useful for scripting.
    for step in $CANONICAL_STEPS; do
      echo "$step"
    done
    ;;

  --get-name)
    if [[ ! -f "$STATE_FILE" ]]; then echo ""; exit 0; fi
    _validate_state
    python3 - "$STATE_FILE" <<'PYEOF'
import json, sys
state = json.load(open(sys.argv[1]))
print(state.get('name', ''))
sys.exit(0)
PYEOF
    ;;

  --get-domain)
    if [[ ! -f "$STATE_FILE" ]]; then echo "feature"; exit 0; fi
    _validate_state
    python3 - "$STATE_FILE" <<'PYEOF'
import json, sys
state = json.load(open(sys.argv[1]))
print(state.get('domain', 'feature'))
sys.exit(0)
PYEOF
    ;;

  --get-lite-mode)
    if [[ ! -f "$STATE_FILE" ]]; then echo "false"; exit 0; fi
    _validate_state
    python3 - "$STATE_FILE" <<'PYEOF'
import json, sys
state = json.load(open(sys.argv[1]))
print(str(state.get('lite_mode', False)).lower())
sys.exit(0)
PYEOF
    ;;

  --get-skills)
    # Returns empty string — skills_available is resolved at orchestrator time.
    echo ""
    ;;

  *)
    echo "Unknown action: $ACTION"
    echo "Valid actions: --init --domain <d> [--lite_mode true|false] [--domain_source <src>] [--skip_phases <csv>] [--force] | --check | --status | --next-step | --step-status <step> | --complete <step> [--pr-url <url>] | --skip <step> | --reset | --get-skip-phases | --get-pr-url | --get-name | --get-domain | --get-lite-mode | --get-skills | --list-phases"
    exit 1
    ;;
esac
