#!/usr/bin/env bash
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKERFILE="$REPO_ROOT/Dockerfile"

echo "=== Static Dockerfile assertions ==="

[[ -f "$DOCKERFILE" ]] || { echo "FAIL: Dockerfile does not exist"; exit 1; }
echo "PASS: Dockerfile exists"

FROM_COUNT=$(grep -c "^FROM " "$DOCKERFILE")
[[ "$FROM_COUNT" -ge 2 ]] || { echo "FAIL: Expected >= 2 FROM lines, got $FROM_COUNT"; exit 1; }
echo "PASS: Multi-stage build ($FROM_COUNT FROM lines)"

grep -q "adduser\|useradd" "$DOCKERFILE" || { echo "FAIL: No user creation (adduser/useradd)"; exit 1; }
echo "PASS: appuser creation present"

grep -q "^USER appuser" "$DOCKERFILE" || { echo "FAIL: USER appuser not set"; exit 1; }
echo "PASS: USER appuser set"

grep -q 'CMD \["python", "-m", "dct_mcp_server.main"\]' "$DOCKERFILE" || { echo "FAIL: CMD not set to python -m dct_mcp_server.main"; exit 1; }
echo "PASS: CMD is python -m dct_mcp_server.main"

grep -q "/app/logs" "$DOCKERFILE" || { echo "FAIL: /app/logs not created"; exit 1; }
echo "PASS: /app/logs present"

grep -q "^LABEL" "$DOCKERFILE" || { echo "FAIL: No LABEL instruction"; exit 1; }
grep -q "maintainer" "$DOCKERFILE" || { echo "FAIL: LABEL missing 'maintainer' field"; exit 1; }
grep -q "version" "$DOCKERFILE" || { echo "FAIL: LABEL missing 'version' field"; exit 1; }
grep -q "description" "$DOCKERFILE" || { echo "FAIL: LABEL missing 'description' field"; exit 1; }
echo "PASS: LABEL present with maintainer, version, description"

grep -q "^EXPOSE" "$DOCKERFILE" && { echo "FAIL: EXPOSE found (stdio server should not expose ports)"; exit 1; } || true
echo "PASS: No EXPOSE (stdio server)"

grep -E "pip install" "$DOCKERFILE" | grep -vE "requirements\.txt|-e \.|pip install \." | grep -v "^#" | grep -q "pip install " && { echo "FAIL: Bare pip install without -r requirements.txt or pip install ."; exit 1; } || true
echo "PASS: pip install lines use requirements.txt or pip install ."

echo "=== All Dockerfile static assertions PASSED ==="
