#!/usr/bin/env bash
# check-structure.sh — Mechanical eval checks for feature-implement
#
# Usage:
#   ./check-structure.sh <NAME> --step <context|design|implement|build|test|pr|release|all>
#
# Examples:
#   ./check-structure.sh TICKET-123 --step all
#   ./check-structure.sh TICKET-123 --step design
#   ./check-structure.sh my-feature --step release

set -euo pipefail

NAME="${1:-}"
STEP="all"
if [[ "${2:-}" == "--step" && -n "${3:-}" ]]; then
  STEP="${3}"
elif [[ -n "${2:-}" && "${2:-}" != "--step" ]]; then
  echo "Warning: expected '--step <name>' as second argument, got '${2}'. Running all steps."
fi

if [[ -z "$NAME" ]]; then
  echo "Usage: $0 <NAME> --step <context|design|implement|build|test|pr|release|all>"
  exit 1
fi

PASS=0
FAIL=0

check() {
  local label="$1"
  local result="$2"
  if [[ "$result" == "pass" ]]; then
    echo "PASS  $label"
    ((++PASS))
  else
    echo "FAIL  $label"
    ((++FAIL))
  fi
}

DESIGN_DOC="docs/${NAME}-design.md"
RELEASE_DOC="docs/${NAME}-doc-updates.md"

echo ""
echo "Checking: $NAME (step: $STEP)"
echo "---"

run_context() {
  echo "[context]"
  check "CLAUDE.md exists"                         "$([[ -f "CLAUDE.md" ]] && echo pass || echo fail)"
  check ".claude/architecture.md exists"           "$([[ -f ".claude/architecture.md" ]] && echo pass || echo fail)"
}

run_design() {
  echo "[design]"
  check "docs/${NAME}-design.md exists"          "$([[ -f "$DESIGN_DOC" ]] && echo pass || echo fail)"
  if [[ ! -f "$DESIGN_DOC" ]]; then
    echo "SKIP  Section checks (file does not exist)"
    return
  fi
  check "## Summary present"                      "$(grep -q '^## Summary' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Affected Components present"          "$(grep -q '^## Affected Components' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Architecture Changes present"         "$(grep -q '^## Architecture Changes' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Version Compatibility present"        "$(grep -q '^## Version Compatibility' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Platform Behavior Notes present"      "$(grep -q '^## Platform Behavior Notes' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Open Questions / Risks present"       "$(grep -q '^## Open Questions' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Acceptance Criteria present"          "$(grep -q '^## Acceptance Criteria' "$DESIGN_DOC" && echo pass || echo fail)"
}

run_implement() {
  echo "[implement]"
  check "At least one file modified"              "$([[ -n "$(git status --porcelain)" ]] && echo pass || echo fail)"
  # Cross-reference files listed in design doc ## Source Files to Modify
  if [[ -f "$DESIGN_DOC" ]]; then
    # Use tracked changes only: staged (cached) + unstaged modified — exclude untracked files to avoid false positives
    MODIFIED=$(git diff --cached --name-only 2>/dev/null; git diff --name-only 2>/dev/null)
    IN_SECTION=0
    while IFS= read -r line; do
      if echo "$line" | grep -q '^### Source Files to Modify'; then
        IN_SECTION=1; continue
      fi
      if [[ $IN_SECTION -eq 1 ]] && echo "$line" | grep -qE '^#{2,3} '; then
        break
      fi
      if [[ $IN_SECTION -eq 1 ]]; then
        FILE=$(echo "$line" | grep -oE '[a-zA-Z0-9_./-]+\.[a-zA-Z]+' | head -1 || true)
        if [[ -n "$FILE" ]]; then
          check "Design file modified: $FILE" \
            "$(echo "$MODIFIED" | grep -qF "$FILE" && echo pass || echo fail)"
        fi
      fi
    done < "$DESIGN_DOC"
  fi
}

run_build() {
  echo "[build]"
  # Detect build command from fenced code blocks in project rules
  BUILD_RULES=".claude/rules/build-and-execution.md"
  BUILD_CMD=""
  if [[ -f "$BUILD_RULES" ]]; then
    # Extract commands from fenced code blocks (```...```) that contain build/compile/package
    BUILD_CMD=$(awk '/^```/{in_block=!in_block; next} in_block{print}' "$BUILD_RULES" \
      | grep -iE '\bbuild\b|\bcompile\b|\bpackage\b' \
      | grep -vE '^\s*#' \
      | head -1 \
      | sed 's/^[[:space:]]*//' \
      | sed 's/[[:space:]]*#.*$//' || true)  # strip trailing comments
  fi
  if [[ -z "$BUILD_CMD" ]]; then
    echo "SKIP  Build checks (no build command found in .claude/rules/build-and-execution.md)"
    return
  fi
  # Validate command is safe — reject shell injection metacharacters (not #, which is a comment)
  if echo "$BUILD_CMD" | grep -qE '[;&|<>$`\\]'; then
    echo "SKIP  Build command contains unsafe characters, skipping execution: $BUILD_CMD"
    return
  fi
  BUILD_OUTPUT=$(eval "$BUILD_CMD" 2>&1); BUILD_EXIT=$?
  check "Build command succeeded (exit 0)"         "$([[ $BUILD_EXIT -eq 0 ]] && echo pass || echo fail)"
  if [[ $BUILD_EXIT -ne 0 ]]; then
    echo "      Build output: $(echo "$BUILD_OUTPUT" | tail -5)"
  fi
  # Check build produced some output (new or modified files)
  CHANGED_AFTER=$(git status --porcelain | wc -l | tr -d ' ')
  check "Build produced output (files changed)"    "$([[ $CHANGED_AFTER -gt 0 ]] && echo pass || echo fail)"
}

run_pr() {
  echo "[pr]"
  GIT_RULES=".claude/rules/git-workflow.md"
  COMMIT_MSG=$(git log -1 --pretty=%s 2>/dev/null || true)
  CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || true)

  # Branch guard — block commits on protected branches or detached HEAD
  PROTECTED_BRANCHES="main master develop"
  if [[ -z "$CURRENT_BRANCH" ]]; then
    check "Not on detached HEAD"                 "fail"
  else
    ON_PROTECTED="pass"
    for branch in $PROTECTED_BRANCHES; do
      if [[ "$CURRENT_BRANCH" == "$branch" ]]; then
        ON_PROTECTED="fail"
        break
      fi
    done
    check "Not on protected branch ($CURRENT_BRANCH)" "$ON_PROTECTED"
  fi

  # Ticket prefix check — extract prefix from git-workflow rules
  if [[ -f "$GIT_RULES" ]]; then
    # Extract first ticket example e.g. PROJ-123 → prefix becomes PROJ, pattern becomes PROJ-[0-9]+
    TICKET_EXAMPLE=$(grep -oE '[A-Z]{2,}-[0-9]+' "$GIT_RULES" | head -1 || true)
    if [[ -n "$TICKET_EXAMPLE" ]]; then
      PREFIX=$(echo "$TICKET_EXAMPLE" | grep -oE '^[A-Z]+')
      TICKET_PATTERN="${PREFIX}-[0-9]+"
    else
      TICKET_PATTERN="[A-Z]+-[0-9]+"
    fi
  else
    TICKET_PATTERN="[A-Z]+-[0-9]+"
  fi
  check "Commit message has ticket prefix"       "$(echo "$COMMIT_MSG" | grep -qE "^$TICKET_PATTERN" && echo pass || echo fail)"

  # Forbidden file check — read from git-workflow rules
  COMMITTED=$(git show --name-only HEAD 2>/dev/null || true)
  if [[ -f "$GIT_RULES" ]]; then
    FORBIDDEN=$(grep -iE 'do not commit|never commit' "$GIT_RULES" | grep -oE '`[^`]+`' | tr -d '`' || true)
    if [[ -n "$FORBIDDEN" ]]; then
      while IFS= read -r pattern; do
        check "\"$pattern\" not in last commit" \
          "$(echo "$COMMITTED" | grep -qF "$pattern" && echo fail || echo pass)"
      done <<< "$FORBIDDEN"
    else
      echo "SKIP  Forbidden file checks (no 'do not commit' patterns found in $GIT_RULES)"
    fi
  else
    echo "SKIP  Forbidden file checks (no $GIT_RULES found)"
  fi
}

run_release() {
  echo "[release]"
  check "docs/${NAME}-doc-updates.md exists"      "$([[ -f "$RELEASE_DOC" ]] && echo pass || echo fail)"
  if [[ ! -f "$RELEASE_DOC" ]]; then
    echo "SKIP  Section checks (file does not exist)"
    return
  fi
  check "## Summary of Change present"            "$(grep -q '^## Summary of Change' "$RELEASE_DOC" && echo pass || echo fail)"
  check "## Pages to Update present"              "$(grep -q '^## Pages to Update' "$RELEASE_DOC" && echo pass || echo fail)"
  check "## Release Notes Entry present"          "$(grep -q '^## Release Notes Entry' "$RELEASE_DOC" && echo pass || echo fail)"
  # Check for internal technical references — file paths and code constructs, not generic words
  INTERNAL=$(grep -cE '\bsrc/[a-zA-Z]|\b[a-zA-Z_]+\.(py|sh)|^(class |def |import |\s+def |\s+class )' "$RELEASE_DOC" || true)
  check "No internal technical references"        "$([[ $INTERNAL -eq 0 ]] && echo pass || echo fail)"
}

run_test_infra_creation() {
  echo "[test-infra-creation]"
  INFRA_FILE=".claude/test-infra.md"

  if [[ ! -f "$INFRA_FILE" ]]; then
    echo "SKIP  .claude/test-infra.md not found — step skipped as expected"
    return
  fi

  check ".claude/test-infra.md exists"             "pass"
  check "test-infra.md is non-empty"               "$([[ -s "$INFRA_FILE" ]] && echo pass || echo fail)"
}

case "$STEP" in
  context)    run_context ;;
  design)     run_design ;;
  implement)  run_implement ;;
  build)      run_build ;;
  test-infra-creation) run_test_infra_creation ;;
  test)       echo "[test]"; echo "SKIP  Test step has no mechanical checks — see criteria/test.md for manual evaluation" ;;
  pr)         run_pr ;;
  release)    run_release ;;
  all)        run_context; run_design; run_implement; run_build; run_test_infra_creation; run_pr; run_release ;;
  *)
    echo "Unknown step: $STEP. Valid: context, design, implement, build, test-infra-creation, test, pr, release, all"
    exit 1
    ;;
esac

echo "---"
echo "Result: $PASS passed, $FAIL failed"
echo ""

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
