#!/usr/bin/env bash
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
README="$REPO_ROOT/README.md"

echo "=== Static README Docker section assertions ==="

[[ -f "$README" ]] || { echo "FAIL: README.md does not exist"; exit 1; }
echo "PASS: README.md exists"

grep -q "## Run with Docker" "$README" || { echo "FAIL: '## Run with Docker' section heading not found"; exit 1; }
echo "PASS: 'Run with Docker' heading present"

TOC_ENTRY=$(grep "run-with-docker\|Run with Docker" "$README" | grep -v "^##" | head -1)
[[ -n "$TOC_ENTRY" ]] || { echo "FAIL: ToC entry for 'Run with Docker' not found"; exit 1; }
echo "PASS: ToC entry present"

grep -q "docker run" "$README" || { echo "FAIL: No 'docker run' command found"; exit 1; }
echo "PASS: docker run command present"

grep "docker run" "$README" | grep " -t " && { echo "FAIL: Found 'docker run ... -t ...' — -t flag breaks stdio MCP transport"; exit 1; } || true
echo "PASS: No -t flag on docker run lines"

grep -q "\-\-init" "$README" || { echo "FAIL: --init flag not documented"; exit 1; }
echo "PASS: --init flag documented"

grep -q '\$env:' "$README" || { echo "FAIL: PowerShell \$env: syntax not found"; exit 1; }
echo "PASS: PowerShell \$env: syntax present"

grep -q '%DCT_API_KEY%\|%VAR%\|%DCT_' "$README" || { echo "FAIL: cmd.exe %VAR% syntax not found"; exit 1; }
echo "PASS: cmd.exe %VAR% syntax present"

grep -q "registry-host" "$README" || { echo "FAIL: Registry placeholder not found"; exit 1; }
echo "PASS: Registry placeholder present"

grep -A5 "registry-host" "$README" | grep -qi "TODO\|pending\|not yet" || { echo "FAIL: Registry placeholder not annotated as TODO/pending"; exit 1; }
echo "PASS: Registry placeholder annotated as TODO/pending"

grep -q '"command": "docker"' "$README" || { echo "FAIL: MCP client JSON snippet with docker command not found"; exit 1; }
echo "PASS: MCP client JSON snippet with docker command present"

grep -q "\-t.*TTY\|\-t.*stdio\|TTY.*\-t\|pseudo-TTY\|pseudo.*tty" "$README" || { echo "FAIL: Troubleshooting note about -t flag not found"; exit 1; }
echo "PASS: Troubleshooting note about -t present"

grep -A 200 "## Run with Docker" "$README" | grep -q "Environment Variables\|#environment-variables" || { echo "FAIL: Docker section does not cross-reference Environment Variables section"; exit 1; }
echo "PASS: Docker section cross-references Environment Variables section"

echo "=== All README Docker static assertions PASSED ==="
