#!/usr/bin/env bash
# Run all test layers L1–L5 and generate a comprehensive HTML report.
# Usage:
#   ./scripts/run_all_tests.sh
#
# Credentials are read from:
#   1. Environment vars DCT_API_KEY, DCT_BASE_URL (already set if running under Claude Code)
#   2. .claude/settings.local.json .env field (auto-loaded by tests/conftest.py)
#
# Set LLM_ALLOW_MUTATION=1 before running to enable L5 mutation tests:
#   LLM_ALLOW_MUTATION=1 CONNECTOR_TYPE=mysql ./scripts/run_all_tests.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS="$REPO_ROOT/test-results"
DATE="$(date '+%Y-%m-%d')"
DATETIME="$(date '+%Y-%m-%d %H:%M')"

mkdir -p "$RESULTS"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     DCT MCP Server — Full Test Suite (L1 → L5)              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo "  Results dir  : $RESULTS"
echo "  Date         : $DATETIME"
echo "  LLM_ALLOW_MUTATION: ${LLM_ALLOW_MUTATION:-0}"
echo "  CONNECTOR_TYPE    : ${CONNECTOR_TYPE:-mysql}"
echo "  DCT_BASE_URL      : ${DCT_BASE_URL:-<from settings.local.json>}"
echo ""

# ── L1 + L2 + L3 ──────────────────────────────────────────────────────────────
echo "▶ L1 + L2 + L3  (unit / integration / functional — no credentials needed)"
caffeinate -i uv run pytest \
    tests/unit tests/integration tests/functional \
    -q --tb=short \
    --json-report --json-report-file="$RESULTS/l123.json" \
    2>&1 | tee "$RESULTS/l123.log" | tail -10
echo ""

# ── L4 — E2E against real DCT, no LLM ─────────────────────────────────────────
echo "▶ L4  (real DCT, no LLM — burns zero tokens)"
caffeinate -i uv run pytest \
    tests/e2e \
    -q --tb=short \
    --json-report --json-report-file="$RESULTS/l4.json" \
    2>&1 | tee "$RESULTS/l4.log" | tail -10
echo ""

# ── L5 — LLM-driven (real DCT + Claude CLI) ───────────────────────────────────
echo "▶ L5  (LLM-driven — real DCT + Claude CLI)"
CONNECTOR_TYPE="${CONNECTOR_TYPE:-mysql}" \
LLM_ALLOW_MUTATION="${LLM_ALLOW_MUTATION:-0}" \
caffeinate -i uv run pytest \
    tests/llm_local \
    -v -s --tb=short \
    --json-report --json-report-file="$RESULTS/l5.json" \
    2>&1 | tee "$RESULTS/l5.log" | tail -20
echo ""

# ── Generate report ────────────────────────────────────────────────────────────
echo "▶ Generating HTML report..."
uv run python scripts/generate_test_report.py \
    --l123 "$RESULTS/l123.json" \
    --l4   "$RESULTS/l4.json" \
    --l5   "$RESULTS/l5.json" \
    --out  "$RESULTS/test-report-${DATE}.html" \
    --date "$DATETIME"

echo ""
echo "✅ Done. Report: $RESULTS/test-report-${DATE}.html"
