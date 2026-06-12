#!/usr/bin/env bash
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKERIGNORE="$REPO_ROOT/.dockerignore"

echo "=== Static .dockerignore assertions ==="

[[ -f "$DOCKERIGNORE" ]] || { echo "FAIL: .dockerignore does not exist"; exit 1; }
echo "PASS: .dockerignore exists"

grep -q "^\.git" "$DOCKERIGNORE" || { echo "FAIL: .git/ not excluded"; exit 1; }
echo "PASS: .git/ excluded"

grep -q "^logs" "$DOCKERIGNORE" || { echo "FAIL: logs/ not excluded"; exit 1; }
echo "PASS: logs/ excluded"

grep -q "__pycache__" "$DOCKERIGNORE" || { echo "FAIL: __pycache__ not excluded"; exit 1; }
echo "PASS: __pycache__ excluded"

grep -q "^\.env" "$DOCKERIGNORE" || { echo "FAIL: .env not excluded"; exit 1; }
echo "PASS: .env excluded"

grep -q "^tests" "$DOCKERIGNORE" || { echo "FAIL: tests/ not excluded"; exit 1; }
echo "PASS: tests/ excluded"

grep -q "^evals" "$DOCKERIGNORE" || { echo "FAIL: evals/ not excluded"; exit 1; }
echo "PASS: evals/ excluded"

grep -q "uv\.lock" "$DOCKERIGNORE" || { echo "FAIL: uv.lock not excluded"; exit 1; }
echo "PASS: uv.lock excluded"

grep -q "^\.claude" "$DOCKERIGNORE" || { echo "FAIL: .claude/ not excluded"; exit 1; }
echo "PASS: .claude/ excluded"

if grep -q "^docs/" "$DOCKERIGNORE" || grep -q "^docs$" "$DOCKERIGNORE"; then
    DOCS_LINE=$(grep -n "^docs" "$DOCKERIGNORE" | tail -1 | cut -d: -f1)
    NEGATION_LINE=$(grep -n "!docs/api-external.yaml" "$DOCKERIGNORE" | head -1 | cut -d: -f1)
    [[ -n "$NEGATION_LINE" ]] || { echo "FAIL: docs/ is excluded but !docs/api-external.yaml negation is missing"; exit 1; }
    [[ "$NEGATION_LINE" -gt "$DOCS_LINE" ]] || { echo "FAIL: !docs/api-external.yaml must appear AFTER docs/ exclusion (Docker processes in order)"; exit 1; }
    echo "PASS: docs/ excluded with correct !docs/api-external.yaml negation ordering"
else
    echo "PASS: No bare docs/ exclusion (api-external.yaml is kept by default)"
fi

echo "=== All .dockerignore static assertions PASSED ==="
