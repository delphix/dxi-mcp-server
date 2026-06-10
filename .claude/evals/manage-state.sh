#!/usr/bin/env bash
# manage-state.sh — Track step completion state for feature-implement workflows
#
# Usage:
#   .claude/evals/manage-state.sh <NAME> --init --domain <domain>
#   .claude/evals/manage-state.sh <NAME> --check
#   .claude/evals/manage-state.sh <NAME> --status
#   .claude/evals/manage-state.sh <NAME> --step-status <step>
#   .claude/evals/manage-state.sh <NAME> --complete <step>
#   .claude/evals/manage-state.sh <NAME> --reset
#
# Exit conventions (--check):
#   exit 0 = no state file found (fresh run)
#   exit 1 = state file found (resume) — note: inverted from POSIX success convention

set -euo pipefail

_script_dir=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || _script_dir=$(dirname "$0")
SCRIPT_PATH="${_script_dir}/$(basename "$0")"

NAME="${1:-}"
ACTION="${2:-}"

if [[ -z "$NAME" || -z "$ACTION" ]]; then
  echo "Usage: $0 <NAME> --init --domain <domain> [--force] | --check | --status | --next-step | --step-status <step> | --complete <step> | --reset"
  exit 1
fi

STATE_FILE=".claude/${NAME}-state.json"

# Validate JSON + schema_version; prints error and exits 2 if corrupt/unknown schema.
# Used by actions that read state so corrupt files are caught early, not just in --check.
_validate_state() {
  if ! python3 - "$STATE_FILE" 2>/dev/null <<'PYEOF'
import json, sys
SUPPORTED_SCHEMAS = {1}
try:
    state = json.load(open(sys.argv[1]))
except Exception:
    print(f"ERROR: state file is not valid JSON", file=sys.stderr)
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
}

case "$ACTION" in
  --init)
    DOMAIN="feature"
    LITE_MODE_VAL="false"
    DOMAIN_SOURCE_VAL=""
    FORCE_FLAG=false
    i=3
    while [[ $i -le $# ]]; do
      case "${!i}" in
        --domain)
          i=$((i+1))
          if [[ $i -gt $# ]]; then echo "ERROR: --domain requires a value"; exit 1; fi
          DOMAIN="${!i}" ;;
        --lite_mode)
          i=$((i+1))
          if [[ $i -gt $# ]]; then echo "ERROR: --lite_mode requires a value (true|false)"; exit 1; fi
          LITE_MODE_VAL="${!i}" ;;
        --domain_source)
          i=$((i+1))
          if [[ $i -gt $# ]]; then echo "ERROR: --domain_source requires a value"; exit 1; fi
          DOMAIN_SOURCE_VAL="${!i}" ;;
        --force)        FORCE_FLAG=true ;;
        --*)            echo "ERROR: unknown flag '${!i}'"; exit 1 ;;
      esac
      i=$((i+1))
    done
    if [[ -z "$DOMAIN" ]]; then
      echo "ERROR: invalid DOMAIN — must be alphanumeric with hyphens/underscores only"
      exit 1
    fi
    if [[ "$LITE_MODE_VAL" != "true" && "$LITE_MODE_VAL" != "false" ]]; then
      echo "ERROR: invalid --lite_mode value '$LITE_MODE_VAL' — must be 'true' or 'false'"
      exit 1
    fi
    if [[ ! "$NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
      echo "ERROR: invalid NAME — must be alphanumeric with hyphens/underscores only"
      exit 1
    fi
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
    python3 - "$NAME" "$DOMAIN" "$LITE_MODE_VAL" "$DOMAIN_SOURCE_VAL" "$STATE_FILE" <<'PYEOF'
import json, sys, os
from datetime import datetime, timezone
name, domain, lite_mode, domain_source, state_file = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
steps = ['context','vision','design','implement','build','test','validate','pr','release','retrospective']
state = {
    'schema_version': 1,
    'name': name,
    'domain': domain,
    'lite_mode': lite_mode == 'true',
    'domain_source': domain_source,
    'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'steps': {s: 'pending' for s in steps},
    'last_completed': '',
    'next_step': 'context'
}
tmp_path = state_file + '.tmp'
with open(tmp_path, 'w') as f:
    json.dump(state, f, indent=2)
os.replace(tmp_path, state_file)
print(f'State initialized for {name} (domain: {domain}, lite_mode: {lite_mode}, schema_version: 1)')
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
    VALID_STEPS="context vision design implement build test validate pr release retrospective"
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
sys.exit(0 if status == 'completed' else 1)
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
ordered = ['context','vision','design','implement','build','test','validate','pr','release','retrospective']
next_step = state.get('next_step', '')
for s in ordered:
    if is_lite and s not in lite_phases:
        print(f'  ▭ {s:<24} skipped')
        continue
    status = state['steps'].get(s, 'pending')
    marker = '\u2713' if status == 'completed' else '\u25cb'
    arrow = '    \u2190 next' if s == next_step else ''
    print(f'  {marker} {s:<24} {status}{arrow}')
PYEOF
    ;;

  --complete)
    STEP="${3:-}"
    if [[ -z "$STEP" ]]; then
      echo "Usage: $0 <NAME> --complete <step>"
      exit 1
    fi
    VALID_STEPS="context vision design implement build test validate pr release retrospective"
    if [[ "$STEP" == *" "* ]] || ! echo "$VALID_STEPS" | grep -qwF "$STEP"; then
      echo "ERROR: unknown step '$STEP'"
      exit 1
    fi
    if [[ ! -f "$STATE_FILE" ]]; then
      echo "WARNING: No state file found for ${NAME} — skipping --complete"
      exit 0
    fi
    _validate_state
    python3 - "$STEP" "$STATE_FILE" <<'PYEOF'
import json, sys, os
step, state_file = sys.argv[1], sys.argv[2]
ordered = ['context','vision','design','implement','build','test','validate','pr','release','retrospective']
lite_phases = {'context', 'implement', 'pr'}
with open(state_file) as f:
    state = json.load(f)
# Idempotent: if already completed, note it and fall through to recompute/persist next_step
already_done = state['steps'].get(step) == 'completed'
if already_done:
    print(f'Note: {step} was already completed — idempotent re-mark (recomputing next_step)')
# Reject out-of-order completion; in lite mode only check non-skipped predecessor phases
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
    if [[ -f "$STATE_FILE" ]]; then
      rm "$STATE_FILE"
      echo "State reset for ${NAME}"
    else
      echo "No state file to reset for ${NAME}"
    fi
    ;;

  *)
    echo "Unknown action: $ACTION"
    echo "Valid actions: --init --domain <d> [--force] | --check | --status | --next-step | --step-status <step> | --complete <step> | --reset"
    exit 1
    ;;
esac
