#!/usr/bin/env bash
# check-structure.sh — Mechanical eval checks for feature-implement
#
# Usage:
#   ./check-structure.sh <NAME> --step <context|vision|design|implement|build|test-infra|test|validate|pr|release|retrospective|consistency|test-citations|all>
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
  echo "Warning: expected '--step <name>' as second argument, got '${2}'. Running all checks."
fi

if [[ -z "$NAME" ]]; then
  echo "Usage: $0 <NAME> --step <context|vision|design|implement|build|test-infra|test|validate|pr|release|retrospective|all>"
  exit 1
fi

PASS=0
FAIL=0

check() {
  local label="$1"
  local result="$2"
  if [[ "$result" == "pass" ]]; then
    echo "PASS  $label"
    ((++PASS))  # prefix ++ required: postfix ((PASS++)) returns 0 when PASS=0, tripping set -e
  else
    echo "FAIL  $label"
    ((++FAIL))  # same: always use prefix ++
  fi
}

# Print body of a section from its header until the next ^## heading.
# The pattern is matched as "${header_pattern}[[:space:]]*$" so '^## Goals' won't
# match '^## Goals and Aspirations'. Callers should NOT include a trailing anchor.
_section_body() {
  local file="$1" header_pattern="$2"
  awk -v pat="${header_pattern}[[:space:]]*\$" '
    $0 ~ pat        { found=1; next }
    found && /^## / { exit }
    found           { print }
  ' "$file"
}

# Like _section_body but without end-anchoring the pattern.
# Use for headings with dynamic suffixes (e.g. '# Spec-Code Coverage: $NAME').
_section_body_loose() {
  local file="$1" header_pattern="$2"
  awk -v pat="$header_pattern" '
    $0 ~ pat        { found=1; next }
    found && /^## / { exit }
    found           { print }
  ' "$file"
}

# Strip HTML comments from stdin, preserving content outside comment delimiters on the same line.
# Handles: inline <!-- ... -->, multi-line comments, and content after --> on closing lines.
_strip_html_comments() {
  awk '
    BEGIN { c = 0 }
    {
      line = $0; out = ""
      while (1) {
        if (c) {
          pos = index(line, "-->")
          if (pos > 0) { line = substr(line, pos + 3); c = 0 }
          else         { line = ""; break }
        } else {
          pos = index(line, "<!--")
          if (pos > 0) { out = out substr(line, 1, pos - 1); line = substr(line, pos + 4); c = 1 }
          else         { out = out line; line = ""; break }
        }
      }
      print out
    }
  '
}

# "pass" if section has ≥1 non-blank, non-HTML-comment, non-scaffold line.
# Scaffold lines: blank, HTML comment, table separators, empty-cell rows, bare N/A / None /
# empty bullets, bare ellipsis, question mark, or common placeholder tokens.
section_has_content() {
  local file="$1" header_pattern="$2"
  _section_body "$file" "$header_pattern" \
    | _strip_html_comments \
    | grep -vE '^[[:space:]]*$' \
    | grep -vE '^[[:space:]]*\|[-|: ]+\|[[:space:]]*$' \
    | grep -vE '^\|([[:space:]]*\|)+[[:space:]]*$' \
    | grep -vivE '^[[:space:]]*(N\/A|None)[[:space:]]*$' \
    | grep -vE '^[[:space:]]*[-*+][[:space:]]*$' \
    | grep -vE '^[[:space:]]*(\.\.\.|\.\.|\?)[[:space:]]*$' \
    | grep -vivE '^[[:space:]]*\((none|n\/a|tbd|to be filled in)\)[[:space:]]*$' \
    | grep -q . && echo pass || echo fail
}

# "pass" if section has at least one markdown table data row (beyond the header + separator)
# A separator row contains only |, -, :, and space characters.
# Empty-cell rows (| | | | |) are also excluded — they count as scaffolding, not content.
section_has_table_data_row() {
  local file="$1" section_pattern="$2"
  _section_body "$file" "$section_pattern" \
    | grep -E '^\|' \
    | grep -vE '^\|([[:space:]]*:?-+:?[[:space:]]*\|)+[[:space:]]*$' \
    | grep -vE '^\|([[:space:]]*\|)+[[:space:]]*$' \
    | awk 'NR > 1' \
    | grep -q . && echo pass || echo fail
}

# "pass" if section has ≥1 table data row OR ≥2 non-empty list items.
# Use for sections where both table and bullet formats are legitimate (e.g. Stakeholders).
section_has_entries() {
  local file="$1" section_pattern="$2"
  local body
  body=$(_section_body "$file" "$section_pattern")
  if echo "$body" \
      | grep -E '^\|' \
      | grep -vE '^\|([[:space:]]*:?-+:?[[:space:]]*\|)+[[:space:]]*$' \
      | awk 'NR > 1' \
      | grep -q .; then
    echo pass
    return
  fi
  local count
  count=$(echo "$body" | { grep -cE '^[[:space:]]*[-*+][[:space:]]+[^[:space:]]' || true; })
  [[ "$count" -ge 2 ]] && echo pass || echo fail
}

# "pass" if section body contains no TBD/TODO/XXX/FIXME tokens (HTML comments excluded)
section_no_placeholders() {
  local file="$1" header_pattern="$2"
  _section_body "$file" "$header_pattern" \
    | _strip_html_comments \
    | sed 's/TBD-[[:alnum:]_-]*//g' \
    | grep -iqE '\bTBD\b|\bTODO\b|\bXXX\b|\bFIXME\b' && echo fail || echo pass
}

DESIGN_DOC="docs/${NAME}/${NAME}-design.md"
RELEASE_DOC="docs/${NAME}/${NAME}-doc-updates.md"

echo ""
echo "Checking: $NAME (step: $STEP)"
echo "---"

run_context() {
  echo "[context]"
  check "CLAUDE.md exists"                         "$([[ -f "CLAUDE.md" ]] && echo pass || echo fail)"
  check ".claude/architecture.md exists"           "$([[ -f ".claude/architecture.md" ]] && echo pass || echo fail)"
}

run_vision() {
  echo "[vision]"
  VISION_DOC="docs/${NAME}/${NAME}-vision.md"
  check "docs/${NAME}/${NAME}-vision.md exists"            "$([[ -f "$VISION_DOC" ]] && echo pass || echo fail)"
  if [[ ! -f "$VISION_DOC" ]]; then
    echo "SKIP  Section checks (file does not exist)"
    return
  fi
  check "## Problem Statement present"             "$(grep -qE '^## Problem Statement[[:space:]]*$' "$VISION_DOC" && echo pass || echo fail)"
  check "## Goals present"                         "$(grep -qE '^## Goals[[:space:]]*$' "$VISION_DOC" && echo pass || echo fail)"
  check "## Non-Goals present"                     "$(grep -qE '^## Non-Goals[[:space:]]*$' "$VISION_DOC" && echo pass || echo fail)"
  check "## Success Criteria present"              "$(grep -qE '^## Success Criteria[[:space:]]*$' "$VISION_DOC" && echo pass || echo fail)"
  check "## Stakeholders present"                  "$(grep -qE '^## Stakeholders[[:space:]]*$' "$VISION_DOC" && echo pass || echo fail)"
  check "## Constraints present"                   "$(grep -qE '^## Constraints[[:space:]]*$' "$VISION_DOC" && echo pass || echo fail)"
  check "Constraints has content"                  "$(section_has_content "$VISION_DOC" '^## Constraints')"
  check "## Risks present"                         "$(grep -qE '^## Risks[[:space:]]*$' "$VISION_DOC" && echo pass || echo fail)"
  check "Problem Statement has content"            "$(section_has_content "$VISION_DOC" '^## Problem Statement')"
  check "Problem Statement no TBD/TODO"            "$(section_no_placeholders "$VISION_DOC" '^## Problem Statement')"
  check "Goals has content"                        "$(section_has_content "$VISION_DOC" '^## Goals')"
  check "Goals no TBD/TODO"                        "$(section_no_placeholders "$VISION_DOC" '^## Goals')"
  check "Non-Goals has content"                    "$(section_has_content "$VISION_DOC" '^## Non-Goals')"
  check "Non-Goals no TBD/TODO"                    "$(section_no_placeholders "$VISION_DOC" '^## Non-Goals')"
  check "Stakeholders has content"                 "$(section_has_content "$VISION_DOC" '^## Stakeholders')"
  check "Stakeholders has entries"                 "$(section_has_entries "$VISION_DOC" '^## Stakeholders')"
  check "Stakeholders no TBD/TODO"                 "$(section_no_placeholders "$VISION_DOC" '^## Stakeholders')"
  check "Constraints no TBD/TODO"                  "$(section_no_placeholders "$VISION_DOC" '^## Constraints')"
  check "Success Criteria has content"             "$(section_has_content "$VISION_DOC" '^## Success Criteria')"
  check "Success Criteria no TBD/TODO"             "$(section_no_placeholders "$VISION_DOC" '^## Success Criteria')"
  check "Risks has content"                        "$(section_has_content "$VISION_DOC" '^## Risks')"
  check "Risks has table data row"                 "$(section_has_table_data_row "$VISION_DOC" '^## Risks')"
  check "Risks no TBD/TODO"                        "$(section_no_placeholders "$VISION_DOC" '^## Risks')"
  FUNCTIONAL_DOC="docs/${NAME}/${NAME}-functional.md"
  if [[ -f "$FUNCTIONAL_DOC" ]]; then
    check "Quality Rules has content"              "$(section_has_content "$FUNCTIONAL_DOC" '^## Quality Rules')"
    check "Edge Cases has content"                 "$(section_has_content "$FUNCTIONAL_DOC" '^## Edge Cases')"
    check "Error Scenarios has content"            "$(section_has_content "$FUNCTIONAL_DOC" '^## Error Scenarios')"
    check "Performance Considerations has content" "$(section_has_content "$FUNCTIONAL_DOC" '^## Performance Considerations')"
  fi
}

run_design() {
  echo "[design]"
  check "docs/${NAME}/${NAME}-design.md exists"          "$([[ -f "$DESIGN_DOC" ]] && echo pass || echo fail)"
  if [[ ! -f "$DESIGN_DOC" ]]; then
    echo "SKIP  Section checks (file does not exist)"
    return
  fi
  check "## Summary present"                      "$(grep -qE '^## Summary[[:space:]]*$' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Affected Components present"          "$(grep -qE '^## Affected Components[[:space:]]*$' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Architecture Changes present"         "$(grep -qE '^## Architecture Changes[[:space:]]*$' "$DESIGN_DOC" && echo pass || echo fail)"
  check "### Source Files to Modify present"      "$(grep -qE '^### Source Files to Modify' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Version Compatibility present"        "$(grep -qE '^## Version Compatibility[[:space:]]*$' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Platform Behavior Notes present"      "$(grep -qE '^## Platform Behavior Notes[[:space:]]*$' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Open Questions / Risks present"       "$(grep -qE '^## Open Questions( / Risks)?[[:space:]]*$' "$DESIGN_DOC" && echo pass || echo fail)"
  check "## Acceptance Criteria present"          "$(grep -qE '^## Acceptance Criteria[[:space:]]*$' "$DESIGN_DOC" && echo pass || echo fail)"
  check "Summary has content"                     "$(section_has_content "$DESIGN_DOC" '^## Summary')"
  check "Summary no TBD/TODO"                     "$(section_no_placeholders "$DESIGN_DOC" '^## Summary')"
  check "Affected Components has content"         "$(section_has_content "$DESIGN_DOC" '^## Affected Components')"
  check "Affected Components no TBD/TODO"        "$(section_no_placeholders "$DESIGN_DOC" '^## Affected Components')"
  check "Architecture Changes has content"        "$(section_has_content "$DESIGN_DOC" '^## Architecture Changes')"
  check "Architecture Changes no TBD/TODO"       "$(section_no_placeholders "$DESIGN_DOC" '^## Architecture Changes')"
  check "Platform Behavior Notes has content"    "$(section_has_content "$DESIGN_DOC" '^## Platform Behavior Notes')"
  check "Platform Behavior Notes no TBD/TODO"    "$(section_no_placeholders "$DESIGN_DOC" '^## Platform Behavior Notes')"
  check "Version Compatibility has content"       "$(section_has_content "$DESIGN_DOC" '^## Version Compatibility')"
  check "Version Compatibility no TBD/TODO"      "$(section_no_placeholders "$DESIGN_DOC" '^## Version Compatibility')"
  check "Open Questions / Risks has content"       "$(_section_body_loose "$DESIGN_DOC" '^## Open Questions' | _strip_html_comments | grep -vE '^[[:space:]]*$' | grep -q . && echo pass || echo fail)"
  check "Acceptance Criteria has content"         "$(section_has_content "$DESIGN_DOC" '^## Acceptance Criteria')"
  check "Acceptance Criteria no TBD/TODO"         "$(section_no_placeholders "$DESIGN_DOC" '^## Acceptance Criteria')"
  check "docs/${NAME}/${NAME}-test-plan.md exists"        "$([[ -f "docs/${NAME}/${NAME}-test-plan.md" ]] && echo pass || echo fail)"
  FUNCTIONAL_DOC="docs/${NAME}/${NAME}-functional.md"
  check "docs/${NAME}/${NAME}-functional.md exists"       "$([[ -f "$FUNCTIONAL_DOC" ]] && echo pass || echo fail)"
  if [[ -f "$FUNCTIONAL_DOC" ]]; then
    check "At least one FR-* requirement present" "$(grep -qE '^## FR-[0-9]+' "$FUNCTIONAL_DOC" && echo pass || echo fail)"
    # Stub detection: every FR-* section must have >=1 real content line.
    # Strip markdown prefixes (bullets, bold labels) then check for placeholder-only content.
    FR_STUB_RESULT="pass"
    while IFS= read -r fr_heading; do
      CONTENT=$(awk -v h="$fr_heading" '
        index($0, h) && /^## FR-/ { found=1; next }
        found && /^## /            { exit }
        found                      { print }
      ' "$FUNCTIONAL_DOC" \
        | grep -vE '^[[:space:]]*$' \
        | grep -vE '^#{1,}' \
        | sed 's/^[[:space:]]*[-*+][[:space:]]\{1,\}//' \
        | sed 's/^[[:space:]]*[*][*][^*]*[*][*]:[[:space:]]*//' \
        | grep -ivE '^[[:space:]]*(TBD|TODO|FIXME|XXX|placeholder|N\/A|None)[[:space:]]*$' \
        | grep -vE '^[[:space:]]*[-*+?][[:space:]]*$' \
        | grep -vE '^[[:space:]]*(\.\.\.|\.\.)[[:space:]]*$' \
        | grep -vivE '^[[:space:]]*\((none|n\/a|tbd|to be filled in)\)[[:space:]]*$' \
        || true)
      if [[ -z "$CONTENT" ]]; then
        FR_STUB_RESULT="fail"
        break
      fi
    done < <(grep -E '^## FR-[0-9]+' "$FUNCTIONAL_DOC")
    check "FR-* sections have non-stub content"   "$FR_STUB_RESULT"
    # FR cross-reference: every FR-* ID in functional.md must appear in Acceptance Criteria
    AC_SECTION=$(_section_body "$DESIGN_DOC" '^## Acceptance Criteria')
    FR_AC_MISSING=0
    while IFS= read -r fr_id; do
      if ! echo "$AC_SECTION" | grep -q "${fr_id}"; then
        echo "WARN  ${fr_id} not referenced in Acceptance Criteria section of design doc"
        ((++FR_AC_MISSING))
      fi
    done < <(grep -oE 'FR-[0-9]+' "$FUNCTIONAL_DOC" | sort -u || true)
    check "All FR-* IDs referenced in Acceptance Criteria" "$([[ $FR_AC_MISSING -eq 0 ]] && echo pass || echo fail)"
  fi
}

run_implement() {
  echo "[implement]"
  # Collect all changed files (staged, unstaged, since HEAD~1, or in first commit)
  _ALL_MODIFIED=$(git diff --cached --name-only 2>/dev/null; git diff --name-only 2>/dev/null; git diff HEAD~1 --name-only 2>/dev/null || true; git show --name-only --pretty=format: HEAD 2>/dev/null || true)
  # Pass only if at least one non-docs file is modified (docs-only commits don't count as implementation)
  _NON_DOCS=$(echo "$_ALL_MODIFIED" | grep -v '^docs/' | grep -v '^$' || true)
  check "At least one non-docs file modified" \
    "$(if [[ -n "$_NON_DOCS" ]]; then echo pass; else echo fail; fi)"
  # Cross-reference files listed in design doc ### Source Files to Modify
  if [[ -f "$DESIGN_DOC" ]]; then
    # Reuse the already-collected modified file list
    MODIFIED="$_ALL_MODIFIED"
    IN_SECTION=0
    SECTION_HAS_TABLE_ROWS=0
    SECTION_HAS_CONTENT=0
    while IFS= read -r line; do
      if echo "$line" | grep -qE '^### `?Source Files to Modify'; then
        IN_SECTION=1; SECTION_HAS_TABLE_ROWS=0; SECTION_HAS_CONTENT=0; continue
      fi
      # Break on any heading (## or deeper) to avoid reading sibling/child subsections
      if [[ $IN_SECTION -eq 1 ]] && echo "$line" | grep -qE '^#{2,} '; then
        if [[ $SECTION_HAS_CONTENT -eq 1 && $SECTION_HAS_TABLE_ROWS -eq 0 ]]; then
          check "'Source Files to Modify' uses table format" "fail"
          echo "      Non-table format prevents file cross-checking — use a markdown table"
        fi
        break
      fi
      if [[ $IN_SECTION -eq 1 ]]; then
        # Track whether section has any non-blank content
        if echo "$line" | grep -qE '[^[:space:]]'; then
          SECTION_HAS_CONTENT=1
        fi
        # Only extract filenames from table rows (lines starting with |) to avoid prose false positives
        if echo "$line" | grep -qE '^\|'; then
          SECTION_HAS_TABLE_ROWS=1
          # Prefer backtick-quoted paths (most unambiguous); backticks are explicit so no extension required
          FILE=$(echo "$line" | grep -oE '`[a-zA-Z0-9_./@()+\-]+`' | tr -d '`' | head -1 || true)
          if [[ -z "$FILE" ]]; then
            # -f2 extracts only the File column (col 2) — avoids false matches on version tokens in other columns
            # Matches: file.ext OR path/with/slash (covers extensionless files like Dockerfile in subdirs)
            # Also matches known extensionless root files: Dockerfile, Makefile, Jenkinsfile, Makefile.*
            FILE=$(echo "$line" | cut -d'|' -f2 | grep -oE '[a-zA-Z0-9_./@()+\-]+\.[a-zA-Z0-9]+|[a-zA-Z0-9_@()+\-]+/[a-zA-Z0-9_./@()+\-]+|Dockerfile[a-zA-Z0-9._-]*|Makefile[a-zA-Z0-9._-]*|Jenkinsfile[a-zA-Z0-9._-]*' | head -1 || true)
          fi
          if [[ -n "$FILE" ]]; then
            FILE="${FILE#./}"  # normalize leading ./ so ./src/x.ts matches src/x.ts in git output
            check "Design file modified: $FILE" \
              "$(echo "$MODIFIED" | awk -v f="$FILE" 'BEGIN { escaped=f; gsub(/[.\[\\*+?{}^$()|]/, "\\\\&", escaped) } ($0==f) || ($0 ~ ("(^|/)" escaped "$"))' | grep -q . && echo pass || echo fail)"
          fi
        fi
      fi
    done < "$DESIGN_DOC"
  fi
}

run_test_generation() {
  echo "[test-generation]"
  # Check that at least one generated test file exists for $NAME.
  # Covers: .spec.ts, .spec.js, .test.ts, .test.js, .test.py, _test.go, -test-suite.json, etc.
  TEST_FILE_FOUND=false
  FOUND_FILE=$(find .claude/test/generated-test \
    \( -name "*${NAME}*.spec.*" -o -name "*${NAME}*.test.*" -o -name "*${NAME}*-test-suite.*" -o -name "*${NAME}*_test.*" \) \
    -print -quit 2>/dev/null || true)
  if [[ -n "$FOUND_FILE" ]]; then
    TEST_FILE_FOUND=true
  fi

  check "Generated test file exists for $NAME" \
    "$([[ "$TEST_FILE_FOUND" == "true" ]] && echo pass || echo fail)"

  if [[ "$TEST_FILE_FOUND" == "true" ]]; then
    # Syntax check for TypeScript files
    if echo "$FOUND_FILE" | grep -qE '\.ts$'; then
      TSC_BIN=""
      if command -v tsc >/dev/null 2>&1; then
        TSC_BIN="tsc"
      elif [[ -x "node_modules/.bin/tsc" ]]; then
        TSC_BIN="node_modules/.bin/tsc"
      fi
      if [[ -n "$TSC_BIN" ]]; then
        set +e
        TSC_OUT=$("$TSC_BIN" --noEmit "$FOUND_FILE" 2>&1); TSC_EXIT=$?
        set -e
        check "TypeScript syntax check passes ($FOUND_FILE)" \
          "$([[ $TSC_EXIT -eq 0 ]] && echo pass || echo fail)"
        if [[ $TSC_EXIT -ne 0 ]]; then
          echo "      tsc output: $(echo "$TSC_OUT" | head -3)"
        fi
      else
        echo "SKIP  TypeScript syntax check (tsc not available)"
      fi
    fi
    # Check for TODO placeholder assertions
    if [[ -f "$FOUND_FILE" ]]; then
      check "No TODO placeholder assertions in test file" \
        "$(grep -qE '//[[:space:]]*TODO' "$FOUND_FILE" && echo fail || echo pass)"
    fi
  fi
}

run_build() {
  echo "[build]"
  # Detect build command from fenced code blocks in project rules
  BUILD_RULES=".claude/rules/build-and-execution.md"
  BUILD_CMD=""
  if [[ -f "$BUILD_RULES" ]]; then
    # Prefer bash/sh tagged fenced blocks; fall back to any fenced block
    BUILD_CMD=$(awk '/^```(bash|sh)[[:space:]]*$/{in_bash=1; next} /^```/{in_bash=0; next} in_bash{print}' "$BUILD_RULES" \
      | grep -iE '\bbuild\b|\bcompile\b|\bpackage\b' \
      | grep -vE '^\s*#' \
      | head -1 \
      | sed 's/^[[:space:]]*//' \
      | sed 's/[[:space:]]*#.*$//' || true)
    if [[ -z "$BUILD_CMD" ]]; then
      BUILD_CMD=$(awk '/^```/{in_block=!in_block; next} in_block{print}' "$BUILD_RULES" \
        | grep -iE '\bbuild\b|\bcompile\b|\bpackage\b' \
        | grep -vE '^\s*#' \
        | head -1 \
        | sed 's/^[[:space:]]*//' \
        | sed 's/[[:space:]]*#.*$//' || true)
    fi
  fi
  if [[ -z "$BUILD_CMD" ]]; then
    echo "SKIP  Build checks (no build command found in .claude/rules/build-and-execution.md)"
    return
  fi
  # Note: we never execute BUILD_CMD — informational only.
  # Safety flags are logged but do NOT skip build-output.md checks.
  if echo "$BUILD_CMD" | grep -qE '[;&|<>$`\\()~]'; then
    echo "INFO  Build command has compound operators (checking output file only): $BUILD_CMD"
  elif echo "$BUILD_CMD" | grep -qE '^/'; then
    echo "INFO  Build command is an absolute path (checking output file only): $BUILD_CMD"
  elif echo "$BUILD_CMD" | grep -qE '(^|\/)\.\.($|\/)'; then
    echo "INFO  Build command has path traversal (checking output file only): $BUILD_CMD"
  fi
  # The executor already ran the build and wrote build-output.md — check that file.
  BUILD_OUTPUT_FILE="docs/${NAME}/${NAME}-build-output.md"
  check "docs/${NAME}/${NAME}-build-output.md exists"     "$([[ -f "$BUILD_OUTPUT_FILE" ]] && echo pass || echo fail)"
  if [[ -f "$BUILD_OUTPUT_FILE" ]]; then
    # Two-condition check: must have a success signal AND no failure signal.
    # Checking the file for any success substring is insufficient because failure outputs
    # often contain partial success tokens (e.g. "0 errors in step 1" then "BUILD FAILED").
    BUILD_HAS_SUCCESS=$(grep -qiE '^[[:space:]]*[*]*Exit code[*]*:[[:space:]]*0\b|^exit[[:space:]]+0|^BUILD SUCCESSFUL|^BUILD SUCCESS' "$BUILD_OUTPUT_FILE" && echo yes || echo no)
    # Failure patterns cover: Maven/Gradle "BUILD FAILED in Xs", "BUILD FAILURE", explicit exit codes,
    # TypeScript/compiler error counts ("3 errors", "error TS2322"), and Maven Surefire test failures.
    # Error count matches at line-start OR after whitespace/open-paren to catch "1 error." and "(1 error)".
    BUILD_HAS_FAILURE=$(grep -qiE '^[[:space:]]*[*]*Exit code[*]*:[[:space:]]*[1-9]|BUILD FAIL(URE|ED)?\b|COMPILATION FAILED|^FAILURE: Build failed|error TS[0-9]+:|Failures:[[:space:]]*[1-9]' "$BUILD_OUTPUT_FILE" \
      && echo yes \
      || { grep -iE '(^|[[:space:](])[1-9][0-9]* errors?\b' "$BUILD_OUTPUT_FILE" \
           | grep -qivE '^[[:space:]]*(fix|found|see|note|run|there|this|please)[[:space:]:]' \
           && echo yes || echo no; })
    check "Build output records success" \
      "$([[ "$BUILD_HAS_SUCCESS" == "yes" && "$BUILD_HAS_FAILURE" == "no" ]] && echo pass || echo fail)"
  fi
}

run_pr() {
  echo "[pr]"
  GIT_RULES=".claude/rules/git-workflow.md"
  # The PR phase creates two commits (code + docs). Check both HEAD and HEAD~1 for the ticket prefix.
  COMMIT_MSG_HEAD=$(git log -1 --pretty=%s 2>/dev/null || true)
  COMMIT_MSG_PREV=$(git log -2 --pretty=%s 2>/dev/null | tail -1 || true)
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

  # Ticket prefix check — skip entirely when $NAME is not a Jira-style ticket ID (e.g. plain-text feature names)
  if ! echo "$NAME" | grep -qE '^[A-Z]{2,}-[0-9]+'; then
    echo "SKIP  Ticket prefix check ($NAME is not a Jira ticket ID — no prefix required)"
  else
  # Ticket prefix check — extract all prefixes from git-workflow rules (supports multiple project prefixes)
  if [[ -f "$GIT_RULES" ]]; then
    # Extract ticket prefixes from lines that define the commit format (e.g. "Commit prefix: PROJ").
    # Extract ticket prefixes only from definition lines (e.g. "Commit prefix: PROJ-123").
    # Negation keywords (do not, never, deprecated, forbidden, example) are excluded first so
    # that "Do not use OLDFOO-456 style" lines don't contribute accepted prefixes.
    PREFIXES=$(grep -iE '(commit prefix|ticket prefix|branch format)[[:space:]]*:?' "$GIT_RULES" \
      | grep -ivE '\bdo not\b|\bdon'\''t\b|\bnever\b|\bdeprecated\b|\bforbidden\b|\bexample\b' \
      | grep -oE '[A-Z]{2,}-[0-9]+' | grep -oE '^[A-Z]+' | sort -u || true)
    # Fallback: if no explicit definition lines found, scan the whole file excluding negation lines
    if [[ -z "$PREFIXES" ]]; then
      PREFIXES=$(grep -ivE '\bdo not\b|\bdon'\''t\b|\bnever\b|\bdeprecated\b|\bforbidden\b' "$GIT_RULES" \
        | grep -oE '[A-Z]{2,}-[0-9]+' | grep -oE '^[A-Z]+' | sort -u || true)
    fi
    if [[ -n "$PREFIXES" ]]; then
      # Build alternation pattern: (PROJ|INF)-[0-9]+
      ALT=$(echo "$PREFIXES" | tr '\n' '|' | sed 's/|$//')
      TICKET_PATTERN="(${ALT})-[0-9]+"
    else
      TICKET_PATTERN="[A-Z]{2,}-[0-9]+"
    fi
  else
    TICKET_PATTERN="[A-Z]{2,}-[0-9]+"
  fi
  # Require ticket ID to be followed by a non-alphanumeric character (colon, space, EOL) to avoid
  # false positives where e.g. PREFIX="PROJ" matches "PROJTOOLS-123"
  # The PR phase creates two commits (code + docs) — pass if EITHER HEAD or HEAD~1 has the ticket prefix.
  TICKET_IN_HEAD=$(echo "$COMMIT_MSG_HEAD" | grep -qE "^${TICKET_PATTERN}([^0-9A-Za-z_]|$)" && echo yes || echo no)
  TICKET_IN_PREV=$(echo "$COMMIT_MSG_PREV" | grep -qE "^${TICKET_PATTERN}([^0-9A-Za-z_]|$)" && echo yes || echo no)
  check "Commit message has ticket prefix (HEAD or HEAD~1)" \
    "$([[ "$TICKET_IN_HEAD" == "yes" || "$TICKET_IN_PREV" == "yes" ]] && echo pass || echo fail)"
  fi  # end: NAME is Jira ticket ID guard

  # Forbidden file check — read from git-workflow rules
  # --pretty=format: suppresses commit metadata so only filenames are matched
  COMMITTED=$(git show --name-only --pretty=format: HEAD 2>/dev/null || true)
  if [[ -f "$GIT_RULES" ]]; then
    FORBIDDEN=$(grep -iE 'do not commit|never commit' "$GIT_RULES" | grep -oE '`[^`]+`' | tr -d '`' || true)
    if [[ -n "$FORBIDDEN" ]]; then
      while IFS= read -r pattern; do
        # Convert shell glob to regex: escape regex metacharacters, then expand glob wildcards
        RE=$(echo "$pattern" | sed 's/[]\[)(}{^$+]/\\&/g; s/\./\\./g; s/\*/.*/g; s/?/./g')
        check "\"$pattern\" not in last commit" \
          "$(echo "$COMMITTED" | grep -qE "(^|/)${RE}$" && echo fail || echo pass)"
      done <<< "$FORBIDDEN"
    else
      echo "SKIP  Forbidden file checks (no 'do not commit' patterns found in $GIT_RULES)"
    fi
  else
    echo "SKIP  Forbidden file checks (no $GIT_RULES found)"
  fi

  # Test evidence embedded in PR body check
  EVIDENCE_DOC="docs/${NAME}/${NAME}-test-evidence.md"
  if [[ -f "$EVIDENCE_DOC" ]]; then
    PR_BODY=""
    # Try gh CLI first
    if command -v gh >/dev/null 2>&1; then
      PR_BODY=$(gh pr view --json body -q .body 2>/dev/null || true)
    fi
    # Fall back to last commit message body
    if [[ -z "$PR_BODY" ]]; then
      PR_BODY=$(git log -1 --pretty=%b 2>/dev/null || true)
    fi
    if [[ -z "$PR_BODY" ]]; then
      echo "SKIP  Test evidence embedded in PR (PR body could not be read)"
    else
      HAS_SCENARIOS=$(echo "$PR_BODY" | grep -qE '^## Functional \(primary\)' && echo yes || echo no)
      HAS_SUMMARY=$(echo "$PR_BODY" | grep -qE '^## Summary' && echo yes || echo no)
      check "PR body contains Functional (primary) section from test evidence" \
        "$([[ "$HAS_SCENARIOS" == "yes" ]] && echo pass || echo fail)"
      check "PR body contains ## Summary section from test evidence" \
        "$([[ "$HAS_SUMMARY" == "yes" ]] && echo pass || echo fail)"
    fi
  else
    echo "SKIP  Test evidence embedded in PR (docs/${NAME}/${NAME}-test-evidence.md does not exist)"
  fi
}

run_release() {
  echo "[release]"
  check "docs/${NAME}/${NAME}-doc-updates.md exists"      "$([[ -f "$RELEASE_DOC" ]] && echo pass || echo fail)"
  if [[ ! -f "$RELEASE_DOC" ]]; then
    echo "SKIP  Section checks (file does not exist)"
    return
  fi
  check "## Summary of Change present"            "$(grep -q '^## Summary of Change' "$RELEASE_DOC" && echo pass || echo fail)"
  check "## Pages to Update present"              "$(grep -q '^## Pages to Update' "$RELEASE_DOC" && echo pass || echo fail)"
  check "## Release Notes Entry present"          "$(grep -q '^## Release Notes Entry' "$RELEASE_DOC" && echo pass || echo fail)"
  check "Summary of Change has content"           "$(section_has_content "$RELEASE_DOC" '^## Summary of Change')"
  check "Summary of Change no TBD/TODO"           "$(section_no_placeholders "$RELEASE_DOC" '^## Summary of Change')"
  check "Pages to Update has content"             "$(section_has_content "$RELEASE_DOC" '^## Pages to Update')"
  check "Pages to Update no TBD/TODO"             "$(section_no_placeholders "$RELEASE_DOC" '^## Pages to Update')"
  check "Release Notes Entry has content"         "$(section_has_content "$RELEASE_DOC" '^## Release Notes Entry')"
  check "Release Notes Entry no TBD/TODO"         "$(section_no_placeholders "$RELEASE_DOC" '^## Release Notes Entry')"
  # Code constructs at line-start indicate developer-facing content leaking into release notes.
  # Ambiguous English words (use, return, export, pub, type, static, public, private, protected)
  # are only matched when followed by a code-specific token, to avoid false positives like
  # "use the new API", "export your data", "return to dashboard", "public release notes".
  INTERNAL=$( { grep -E \
    '^(class |def |import |func |interface |fn |impl |const |let |var |function )'\
'|^export[[:space:]]+(default|const|function|class|interface|type|\{|let|var)'\
'|^(public|private|protected)[[:space:]]+(class|interface|void|boolean|int|long|String|Integer|double|float|char|byte|short|abstract|static|final|synchronized)'\
'|^package[[:space:]]+[a-z]'\
'|^[[:space:]]+(def|class|func|fn|impl|const|let|var|function)[[:space:]]' \
    "$RELEASE_DOC" 2>/dev/null || true; } | wc -l | tr -d ' ')
  check "No code constructs in Release Notes" "$([[ $INTERNAL -eq 0 ]] && echo pass || echo fail)"
  [[ $INTERNAL -gt 0 ]] && echo "      Release Notes contains code-like lines — rewrite in user-facing language" || true
}


run_test_citations() {
  # Verify that PASS rows in coverage.md have real file:line evidence (not fabricated citations).
  # Parses the Evidence column (col 5 in "| FR-ID | Desc | Status | Evidence |" table),
  # checks the cited file exists, and verifies the cited line number is within bounds.
  COVERAGE_DOC="docs/${NAME}/${NAME}-coverage.md"
  if [[ ! -f "$COVERAGE_DOC" ]]; then
    echo "SKIP  Citation checks (docs/${NAME}/${NAME}-coverage.md does not exist)"
    return
  fi
  CITE_PASS=0
  CITE_FAIL=0
  while IFS= read -r row; do
    STATUS=$(echo "$row" | awk -F'|' '{
      for(i=1; i<=NF; i++) {
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", $i)
        up=toupper($i)
        if(up=="PASS"||up=="FAIL"||up=="SKIPPED"||up=="N/A") { print up; break }
      }
    }')
    [[ "$STATUS" != "PASS" ]] && continue
    EVIDENCE=$(echo "$row" | awk -F'|' '{
      for(i=1; i<=NF; i++) {
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", $i)
        up=toupper($i)
        if(up=="PASS"||up=="FAIL"||up=="SKIPPED"||up=="N/A") {
          if(i+1<=NF) { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $(i+1)); print $(i+1) }
          break
        }
      }
    }')
    # Skip explicit "none" citations — these are FAIL rows masquerading as evidence-absent PASS;
    # a PASS row with "none" evidence is itself a violation caught separately
    if echo "$EVIDENCE" | grep -qiE '^none|^N/?A$|^-$|^$'; then
      echo "WARN  PASS row has no file:line evidence: $(echo "$row" | cut -d'|' -f2 | tr -d ' ')"
      ((++CITE_FAIL))
      continue
    fi
    # Extract first file:line pattern — supports "path/to/file.ext:N" and "file.ext:N (text)"
    CITE_FILE=$(echo "$EVIDENCE" | grep -oE '[a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+:[0-9]+' | head -1 | cut -d: -f1 || true)
    CITE_LINE=$(echo "$EVIDENCE" | grep -oE '[a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+:[0-9]+' | head -1 | cut -d: -f2 || true)
    if [[ -z "$CITE_FILE" ]]; then
      echo "WARN  Cannot parse file:line from evidence: $EVIDENCE"
      ((++CITE_FAIL))
      continue
    fi
    if [[ ! -f "$CITE_FILE" ]]; then
      echo "FAIL  Cited file does not exist: $CITE_FILE"
      ((++CITE_FAIL))
      continue
    fi
    if [[ -n "$CITE_LINE" && "$CITE_LINE" =~ ^[0-9]+$ ]]; then
      FILE_LINES=$(wc -l < "$CITE_FILE" | tr -d ' ')
      if [[ "$CITE_LINE" -gt "$FILE_LINES" ]]; then
        echo "FAIL  Citation line $CITE_LINE out of range in $CITE_FILE ($FILE_LINES lines)"
        ((++CITE_FAIL))
        continue
      fi
    fi
    ((++CITE_PASS))
  done < <(grep -E '^\| FR-[0-9]+' "$COVERAGE_DOC" 2>/dev/null || true)

  if [[ $((CITE_PASS + CITE_FAIL)) -eq 0 ]]; then
    echo "SKIP  No PASS rows with evidence to verify"
    return
  fi
  check "Coverage PASS citations are real file:line refs" "$([[ $CITE_FAIL -eq 0 ]] && echo pass || echo fail)"
  [[ $CITE_FAIL -gt 0 ]] && echo "      $CITE_FAIL citation(s) failed — see FAIL/WARN lines above" || true
}

run_test_infra() {
  echo "[test-infra]"
  INFRA_DOC=".claude/test/test-infra.md"
  if [[ ! -f "$INFRA_DOC" ]]; then
    echo "SKIP  test-infra checks (no .claude/test/test-infra.md found)"
    return
  fi
  check "test-infra.md is non-empty" "$([[ -s "$INFRA_DOC" ]] && echo pass || echo fail)"
  # If a ## VMs section exists, verify each table row has at least a non-empty Name column
  if grep -qE '^## VMs' "$INFRA_DOC"; then
    VM_ROWS=$(awk '/^## VMs/{flag=1;next} flag && /^## /{exit} flag' "$INFRA_DOC" \
      | grep -E '^\|' | grep -vE '^\|[[:space:]]*[-:]+' | awk 'NR>1' || true)
    VM_COUNT=$(echo "$VM_ROWS" | grep -c . || true)
    check "## VMs section has at least one VM entry" "$([[ $VM_COUNT -ge 1 ]] && echo pass || echo fail)"
    # Each row must have a non-empty first data column (VM name)
    UNNAMED=$(echo "$VM_ROWS" | awk -F'|' '{ name=$2; gsub(/^[[:space:]]+|[[:space:]]+$/,"",name); if(name=="") print $0 }' | grep -c . || true)
    check "All VM entries have a name" "$([[ $UNNAMED -eq 0 ]] && echo pass || echo fail)"
  fi
}

run_test() {
  echo "[test]"
  EVIDENCE_DOC="docs/${NAME}/${NAME}-test-evidence.md"
  COVERAGE_DOC="docs/${NAME}/${NAME}-coverage.md"

  check "docs/${NAME}/${NAME}-test-evidence.md exists"     "$([[ -f "$EVIDENCE_DOC" ]] && echo pass || echo fail)"
  check "docs/${NAME}/${NAME}-coverage.md exists"          "$([[ -f "$COVERAGE_DOC" ]] && echo pass || echo fail)"

  if [[ -f "$COVERAGE_DOC" ]]; then
    check "Coverage has FR-* rows"                 "$(grep -qE '^\| FR-[0-9]+' "$COVERAGE_DOC" && echo pass || echo fail)"
    check "Coverage no TBD/TODO"                   "$(grep -iqE '\bTBD\b|\bTODO\b' "$COVERAGE_DOC" && echo fail || echo pass)"
    run_test_citations

    # Verify every FR defined in functional.md has a corresponding row in coverage.md
    FUNCTIONAL_DOC="docs/${NAME}/${NAME}-functional.md"
    if [[ -f "$FUNCTIONAL_DOC" ]]; then
      FR_MISSING=0
      while IFS= read -r fr_id; do
        if ! grep -qE "^\|[[:space:]]+${fr_id}[[:space:]]*\|" "$COVERAGE_DOC"; then
          echo "WARN  ${fr_id} defined in functional.md has no row in coverage.md"
          ((++FR_MISSING))
        fi
      done < <(grep -E '^## FR-[0-9]+' "$FUNCTIONAL_DOC" | grep -oE 'FR-[0-9]+' | sort -u)
      check "All FR-* IDs have coverage rows" "$([[ $FR_MISSING -eq 0 ]] && echo pass || echo fail)"
      [[ $FR_MISSING -gt 0 ]] && echo "      $FR_MISSING FR(s) missing from coverage — see WARN lines above" || true

      # Reverse check: every coverage row must reference a real FR-* from functional.md
      ORPHAN_COUNT=0
      while IFS= read -r cov_fr; do
        if ! grep -qE "^## ${cov_fr}([[:space:]]|$)" "$FUNCTIONAL_DOC"; then
          echo "WARN  Coverage row for ${cov_fr} has no matching FR-* in functional.md (fabricated?)"
          ((++ORPHAN_COUNT))
        fi
      done < <(awk -F'|' 'NR>2 { col=$2; gsub(/^[[:space:]]+|[[:space:]]+$/, "", col); if (col ~ /^FR-[0-9]/) print col }' "$COVERAGE_DOC" | sort -u || true)
      check "Coverage rows reference known FR-* IDs" "$([[ $ORPHAN_COUNT -eq 0 ]] && echo pass || echo fail)"
      [[ $ORPHAN_COUNT -gt 0 ]] && echo "      $ORPHAN_COUNT coverage row(s) cite unknown FR-IDs — see WARN lines above" || true
    fi
  fi

  if [[ -f "$EVIDENCE_DOC" ]]; then
    check "Test evidence has Functional (primary) section" "$(grep -qE '^## Functional \(primary\)[[:space:]]*$' "$EVIDENCE_DOC" && echo pass || echo fail)"
    check "Test evidence has Outcome entries"      "$(grep -qE '^\|.*\|[[:space:]]*(PASS|FAIL|SKIPPED)[[:space:]]*\|' "$EVIDENCE_DOC" && echo pass || echo fail)"
    # For every table row containing SKIPPED, verify that at least one column after the SKIPPED cell
    # is non-empty (i.e. a reason/notes field exists regardless of column position).
    SKIPPED_NO_REASON=$( { grep -iE '^\|.*SKIPPED' "$EVIDENCE_DOC" || true; } | \
      awk -F'|' '{
        found=0
        for(i=2;i<=NF-1;i++) {
          cell=$i; gsub(/^[[:space:]]+|[[:space:]]+$/,"",cell)
          if(toupper(cell)=="SKIPPED") { found=i }
        }
        if(found>0) {
          has_reason=0
          for(i=found+1;i<=NF-1;i++) {
            cell=$i; gsub(/^[[:space:]]+|[[:space:]]+$/,"",cell)
            if(cell!="") { has_reason=1 }
          }
          if(!has_reason) print $0
        }
      }' | wc -l | tr -d ' ')
    check "SKIPPED scenarios have a reason column" "$([[ "$SKIPPED_NO_REASON" -eq 0 ]] && echo pass || echo fail)"
    [[ "$SKIPPED_NO_REASON" -gt 0 ]] && echo "      $SKIPPED_NO_REASON SKIPPED row(s) have an empty reason/notes column" || true
    check "Test evidence has Summary section"      "$(grep -qE '^## Summary' "$EVIDENCE_DOC" && echo pass || echo fail)"
  fi
}

run_validate() {
  echo "[validate]"
  FUNCTIONAL_DOC="docs/${NAME}/${NAME}-functional.md"
  COVERAGE_DOC="docs/${NAME}/${NAME}-coverage.md"
  VALIDATION_DOC="docs/${NAME}/${NAME}-validation.md"

  check "docs/${NAME}/${NAME}-functional.md exists"       "$([[ -f "$FUNCTIONAL_DOC" ]] && echo pass || echo fail)"
  check "docs/${NAME}/${NAME}-coverage.md exists"         "$([[ -f "$COVERAGE_DOC" ]] && echo pass || echo fail)"
  check "docs/${NAME}/${NAME}-validation.md exists"       "$([[ -f "$VALIDATION_DOC" ]] && echo pass || echo fail)"

  if [[ -f "$VALIDATION_DOC" ]]; then
    check "FR Coverage section present"           "$(grep -qE '## 1\. Functional Requirement Coverage|## FR Coverage' "$VALIDATION_DOC" && echo pass || echo fail)"
    check "Quality Rule Enforcement section present" "$(grep -qE '## 2\. Quality|## Quality Rule' "$VALIDATION_DOC" && echo pass || echo fail)"
    check "Task Completion section present"       "$(grep -qE '## 3\. Task Completion|## Task Completion' "$VALIDATION_DOC" && echo pass || echo fail)"
    check "Issues Found section present"          "$(grep -qE '## 4\. Issues|## Issues Found' "$VALIDATION_DOC" && echo pass || echo fail)"
    check "Security Assessment section present"   "$(grep -qE '## 5\. Security|## Security' "$VALIDATION_DOC" && echo pass || echo fail)"
    check "Code Quality section present"          "$(grep -qE '## 6\. Code Quality|## Code Quality' "$VALIDATION_DOC" && echo pass || echo fail)"
    check "Build and Test Results section present" "$(grep -qE '## 7\. Build|## Build.*Test' "$VALIDATION_DOC" && echo pass || echo fail)"
    check "Build and Test Results has content"    "$(section_has_content "$VALIDATION_DOC" '^## 7[.]|^## Build')"
    check "Recommendations section present"       "$(grep -qE '## 8\. Recommendations|## Recommendations' "$VALIDATION_DOC" && echo pass || echo fail)"
    check "Overall Verdict present"               "$(grep -qiE 'Verdict.*(PASS|FAIL)|Overall Verdict' "$VALIDATION_DOC" && echo pass || echo fail)"
    check "Overall Verdict populated"             "$(grep -qE '^\*\*(Overall )?Verdict:\*\*[[:space:]]*`?(PASS WITH WARNINGS|PASS|FAIL)`?[[:space:]]*(—.*)?[[:space:]]*$|^\*\*(Overall )?Verdict\*\*:[[:space:]]*`?(PASS WITH WARNINGS|PASS|FAIL)`?[[:space:]]*(—.*)?[[:space:]]*$' "$VALIDATION_DOC" && echo pass || echo fail)"
    check "E2E results section present"           "$(grep -qiE '^## 9[.:][[:space:]].*e2e|^## 9[.:][[:space:]].*end.to.end|^## E2E\b' "$VALIDATION_DOC" && echo pass || echo fail)"
    check "E2E results section has content"       "$(section_has_content "$VALIDATION_DOC" '^## 9[.]|^## E2E\b')"
    check "Quality Rule Enforcement has rows"     "$(awk '/^## 2\. Quality/{flag=1; next} flag && /^## [0-9]+\./{exit} flag' "$VALIDATION_DOC" | awk -F'|' 'NF>2 { rule=$2; gsub(/^[[:space:]]+|[[:space:]]+$/, "", rule); if (rule != "" && ($0 ~ /PASS|FAIL/)) { found=1 } } END { exit !found }' && echo pass || echo fail)"

    # Cross-check: a PASS verdict must not contradict Critical issues anywhere in the doc or FAIL rows in FR Coverage
    VERDICT=$(grep -iE '^\*\*(Overall )?Verdict' "$VALIDATION_DOC" \
              | grep -oE 'PASS WITH WARNINGS|PASS|FAIL' | head -1 || true)
    if [[ "$VERDICT" == "PASS" || "$VERDICT" == "PASS WITH WARNINGS" ]]; then
      # Detect Critical items anywhere in the document — handles all common formats:
      #   ## / ### headings: any heading containing "critical" (Critical Findings, Critical:, etc.)
      #   table rows:   "| ... | Critical | ..."  or  "| ... | Severity: Critical | ..."
      #   bold patterns: "**Critical**:", "**Critical Issue:**", "**Severity:** Critical"
      #   bold-label patterns: "**Severity**: Critical" (bold label, colon/value outside)
      #   italic patterns: "*Critical*:", "_Critical_:"
      #   bracket tags: "- [Critical] ..." (any list marker, any case)
      #   parenthesized: "- (Critical) ..." (list item)
      #   inline text:  "Severity/Priority/Impact/Rating: critical" anywhere in prose
      #   list bullets:  "-", "*", "+" or "N." prefixed "Critical:" (any case, optional emoji/symbol prefix)
      #   bare prose / blockquote: "Critical: text", "> Critical: text", "> [!CAUTION] Critical: text"
      HAS_CRITICAL=$(awk '
        # Any heading (2+ hashes) containing "critical" (but not "non-critical")
        tolower($0) ~ /^##+[[:space:]]/ && tolower($0) ~ /critical/ && tolower($0) !~ /non-critical/ { in_crit=1; next }
        in_crit && /^#/ { in_crit=0 }
        in_crit && /^[-*+0-9]/ { print "yes"; exit }
        # Table rows with Critical as a severity/status cell
        /^\|/ && tolower($0) ~ /\|[[:space:]]*(severity:[[:space:]]*)?critical[[:space:]]*\|/ { print "yes"; exit }
        # Bold patterns — colon may appear inside or outside the closing **
        tolower($0) ~ /\*\*critical([[:space:]]+issues?)?:?\*\*:?/ { print "yes"; exit }
        # Severity/Priority/Impact/Rating dimension: plain or bold label with colon or equals separator
        tolower($0) ~ /(severity|priority|impact|rating)[[:space:]]*[:=][[:space:]]*\**[[:space:]]*critical/ { print "yes"; exit }
        tolower($0) ~ /\*\*(severity|priority|impact|rating)\*\*[[:space:]]*[:=][[:space:]]*critical/ { print "yes"; exit }
        # HTML bold/strong: <strong>Critical:</strong> or <b>Critical</b>
        tolower($0) ~ /<(strong|b)>[[:space:]]*critical/ { print "yes"; exit }
        # Bracket tag any case, any list marker
        /^[-*+][[:space:]]+\[([Cc][Rr][Ii][Tt][Ii][Cc][Aa][Ll])\]/ { print "yes"; exit }
        # Plain, emoji-prefixed, italic (*Critical*:/_Critical_:), or parenthesized Critical list item
        # Separator class includes ASCII dash, em-dash (—), and en-dash (–)
        tolower($0) ~ /^[-*+][[:space:]]+([^[:alnum:][:space:]][[:space:]]*)?[\*_]?critical[\*_]?[[:space:]]*[:,()\-—–]/ { print "yes"; exit }
        # Numbered list "1. Critical:/_Critical_:/(Critical)" (any case)
        tolower($0) ~ /^[0-9]+\.[[:space:]]+([^[:alnum:][:space:]][[:space:]]*)?[\*_]?critical[\*_]?[[:space:]]*[:,()\-—–]/ { print "yes"; exit }
        # Parenthesized standalone: - (Critical) text
        tolower($0) ~ /^[-*+0-9.][[:space:]]+\(critical\)[[:space:]]/ { print "yes"; exit }
        # Bare prose / blockquote: "Critical:", "> Critical:", "> [!CAUTION] Critical:"
        tolower($0) ~ /^[[:space:]]*(>[[:space:]]*(\[[^]]*\][[:space:]]*)?)?[\*_]?critical[\*_]?[[:space:]]*:/ { print "yes"; exit }
      ' "$VALIDATION_DOC" 2>/dev/null || true)
      check "Verdict has no Critical issues in doc" \
        "$([[ -z "$HAS_CRITICAL" ]] && echo pass || echo fail)"
      [[ -n "$HAS_CRITICAL" ]] && echo "      Verdict is $VERDICT but doc contains Critical issue(s)" || true

      # Detect FAIL rows in FR Coverage (coverage.md or Section 1 of validation.md)
      if [[ -f "$COVERAGE_DOC" ]]; then
        FR_FAILS=$( { grep -iE '^\| FR-[0-9]+[^|]*\|[^|]*\| *FAIL' "$COVERAGE_DOC" 2>/dev/null || true; } | wc -l | tr -d ' ')
        check "PASS verdict has no FR Coverage FAIL rows" \
          "$([[ "$FR_FAILS" -eq 0 ]] && echo pass || echo fail)"
        [[ "$FR_FAILS" -gt 0 ]] && echo "      Verdict is PASS but FR Coverage has $FR_FAILS FAIL row(s)" || true
      fi
      # Also scan Section 1 of validation.md itself — catches FAIL rows when no coverage.md exists
      # Section 1 format: "| FR-ID | Status | Notes |" — FAIL appears in field 2 (one pipe after FR-ID)
      FR_FAILS_IN_VAL=$( { awk '/^## 1[.:]? /{flag=1; next} flag && /^## [0-9]+[.:]?/{exit} flag' \
        "$VALIDATION_DOC" 2>/dev/null | grep -iE '^\|[^|]*FR-[0-9]+[^|]*\| *FAIL' || true; } \
        | wc -l | tr -d ' ')
      if [[ "$FR_FAILS_IN_VAL" -gt 0 ]]; then
        check "PASS verdict has no FR FAIL rows in validation Section 1" "fail"
        echo "      Verdict is $VERDICT but validation doc Section 1 has $FR_FAILS_IN_VAL FAIL row(s)"
      fi
    fi
  fi

  if [[ -f "$FUNCTIONAL_DOC" ]]; then
    check "At least one FR-* requirement present" "$(grep -qE '^## FR-[0-9]+' "$FUNCTIONAL_DOC" && echo pass || echo fail)"
  fi
}

run_retrospective() {
  echo "[retrospective]"
  RETRO_FILE=".claude/retrospectives.md"
  check ".claude/retrospectives.md exists"         "$([[ -f "$RETRO_FILE" ]] && echo pass || echo fail)"
  if [[ -f "$RETRO_FILE" ]]; then
    # Accept both "## NAME" and "## NAME — 2026-04-27" (executor appends em-dash + date)
    check "Entry for $NAME present"                "$(grep -qE "^## ${NAME}([[:space:]]+(—|--|–).*)?[[:space:]]*$" "$RETRO_FILE" && echo pass || echo fail)"
    # Extract the $NAME section and verify each of the 3 answers has >10 non-whitespace chars.
    # Capture text on the question line itself (after "N. ") AND any continuation lines.
    SECTION=$(awk "/^## ${NAME}([[:space:]]+(—|--|–))?/{found=1; next} found && /^## /{exit} found{print}" "$RETRO_FILE")
    for Q in 1 2 3; do
      ANSWER=$(echo "$SECTION" | awk -v q="$Q" '
        /^[0-9]+\./ { n++; found=(n==q); if(found){ sub(/^[0-9]+\. */,""); print; next } else { found=0 } }
        found && /^[0-9]+\./ { exit }
        found { print }
      ' | tr -d '[:space:]')
      CHARS=${#ANSWER}
      check "Q${Q} answer has >10 non-whitespace chars" "$([[ $CHARS -gt 10 ]] && echo pass || echo fail)"
    done
  fi
}

run_consistency() {
  echo "[consistency]"
  # Verify that VALID_STEPS in manage-state.sh matches the canonical step list in check-structure.sh
  MANAGE_STATE=".claude/evals/manage-state.sh"
  # Dev fallback: when scripts live alongside check-structure.sh (evals/scripts/) before plugin bootstrap
  _cs_dir=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || dirname "$0")
  if [[ ! -f "$MANAGE_STATE" && -f "${_cs_dir}/manage-state.sh" ]]; then
    MANAGE_STATE="${_cs_dir}/manage-state.sh"
  fi
  if [[ -f "$MANAGE_STATE" ]]; then
    EXPECTED="context vision design implement build test-infra test validate pr release retrospective"
    # Extract all occurrences of VALID_STEPS and deduplicate — catches drift across multiple definitions
    MANAGE_STEPS_UNIQ=$(grep 'VALID_STEPS=' "$MANAGE_STATE" | grep -oE '"[^"]+"' | tr -d '"' | sort -u || true)
    UNIQUE_COUNT=$(echo "$MANAGE_STEPS_UNIQ" | grep -c . || true)
    check "manage-state VALID_STEPS matches canonical list" \
      "$([[ "$UNIQUE_COUNT" -eq 1 && "$MANAGE_STEPS_UNIQ" == "$EXPECTED" ]] && echo pass || echo fail)"
    [[ "$UNIQUE_COUNT" -gt 1 ]] && echo "      VALID_STEPS definitions drift: $UNIQUE_COUNT distinct values found" || true
    # Also check the Python steps = [...] list in the --init block
    PYINIT_STEPS=$(grep "^steps = \[" "$MANAGE_STATE" \
      | grep -oE "'[a-z-]+'" | tr -d "'" | tr '\n' ' ' | sed 's/ $//' || true)
    check "manage-state Python steps list matches canonical list" \
      "$([[ "$PYINIT_STEPS" == "$EXPECTED" ]] && echo pass || echo fail)"
  else
    echo "SKIP  Consistency check (manage-state.sh not found at $MANAGE_STATE)"
  fi
  # Verify key state file schema integrity
  STATE_FILE=".claude/${NAME}-state.json"
  if [[ -f "$STATE_FILE" ]]; then
    check "State file is valid JSON" \
      "$(python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$STATE_FILE" 2>/dev/null && echo pass || echo fail)"
    check "State file has schema_version" \
      "$(python3 -c 'import json,sys; s=json.load(open(sys.argv[1])); assert s.get("schema_version") == 1' "$STATE_FILE" 2>/dev/null && echo pass || echo fail)"
  fi
  # Verify agent files contain load-bearing contract strings so future edits don't silently remove guards
  # Search parent dirs first (dev layout: agents/ is a sibling of skills/); fallback to plugin cache
  ORCHESTRATOR=""
  _search_dir="${_cs_dir}"
  for _i in 1 2 3 4 5; do
    _search_dir="$(dirname "$_search_dir")"
    if [[ -f "${_search_dir}/agents/feature-orchestrator.md" ]]; then
      ORCHESTRATOR="${_search_dir}/agents/feature-orchestrator.md"
      break
    fi
  done
  if [[ -z "$ORCHESTRATOR" ]]; then
    ORCHESTRATOR=$(find .claude/plugins/cache ~/.claude/plugins/cache -name "feature-orchestrator.md" -path "*/agents/*" 2>/dev/null | head -1 || true)
  fi
  if [[ -f "$ORCHESTRATOR" ]]; then
    check "Orchestrator is context-only (no executor dispatch)" \
      "$(grep -q 'context phase only\|context phase only\|context.*only' "$ORCHESTRATOR" && echo pass || echo fail)"
    check "Orchestrator has --skip parsing or writes context result.json" \
      "$(grep -q 'SKIP_PHASES\|result\.json' "$ORCHESTRATOR" && echo pass || echo fail)"
  else
    echo "SKIP  Agent contract checks (feature-orchestrator.md not found)"
  fi
  EXECUTOR=""
  _search_dir="${_cs_dir}"
  for _i in 1 2 3 4 5; do
    _search_dir="$(dirname "$_search_dir")"
    if [[ -f "${_search_dir}/agents/feature-executor.md" ]]; then
      EXECUTOR="${_search_dir}/agents/feature-executor.md"
      break
    fi
  done
  if [[ -z "$EXECUTOR" ]]; then
    EXECUTOR=$(find .claude/plugins/cache ~/.claude/plugins/cache -name "feature-executor.md" -path "*/agents/*" 2>/dev/null | head -1 || true)
  fi
  if [[ -f "$EXECUTOR" ]]; then
    check "Executor has SPEC-EXISTENCE-GATE" \
      "$(grep -q 'SPEC-EXISTENCE-GATE' "$EXECUTOR" && echo pass || echo fail)"
    check "Executor has NO-DIRECT-IMPLEMENTATION guard" \
      "$(grep -q 'NO-DIRECT-IMPLEMENTATION' "$EXECUTOR" && echo pass || echo fail)"
    check "Executor has POST-GATE check" \
      "$(grep -q 'POST-GATE\|post-gate\|post gate' "$EXECUTOR" && echo pass || echo fail)"
  else
    echo "SKIP  Executor contract checks (feature-executor.md not found)"
  fi
}

case "$STEP" in
  context)          run_context ;;
  vision)           run_vision ;;
  design)           run_design ;;
  implement)        run_implement ;;
  build)            run_build ;;
  test-generation)  run_test_generation ;;
  test-infra)       run_test_infra ;;
  test)             run_test ;;
  validate)         run_validate ;;
  pr)               run_pr ;;
  release)          run_release ;;
  retrospective)    run_retrospective ;;
  consistency)      run_consistency ;;
  test-citations)   run_test_citations ;;

  all)
    LITE_ALL=false
    if [[ -f ".claude/${NAME}-state.json" ]]; then
      LITE_ALL=$(python3 -c "import json,sys; s=json.load(open(sys.argv[1])); print('true' if s.get('lite_mode') else 'false')" ".claude/${NAME}-state.json" 2>/dev/null || echo false)
    fi
    run_consistency
    if [[ "$LITE_ALL" == "true" ]]; then
      run_context; run_implement; run_pr
    else
      run_context; run_vision; run_design; run_implement; run_build; run_test_generation; run_test_infra; run_test; run_validate; run_pr; run_release; run_retrospective
    fi
    ;;
  *)
    echo "Unknown step: $STEP. Valid: context, vision, design, implement, build, test-infra, test, validate, pr, release, retrospective, consistency, test-citations, all"
    exit 1
    ;;
esac

echo "---"
echo "Result: $PASS passed, $FAIL failed"
echo ""

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
