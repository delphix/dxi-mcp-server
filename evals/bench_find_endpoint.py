#!/usr/bin/env python3
"""
Benchmark for find_endpoint's hot path: OLD (rebuild + nested scan per call) vs
NEW (precomputed discovery index + reverse toolset index).

Two layers are measured so the speedup can be attributed:

  1. RANKING only — corpus build + hot-keyword extraction + per-candidate
     tokenisation + scoring. OLD rebuilds all of this every call; NEW reuses the
     cached discovery index.

  2. END-TO-END — ranking PLUS resolving each ranked candidate's
     suggested_toolset. OLD rescans every toolset/tool/api per candidate; NEW
     does an O(1) reverse-index lookup. This is the representative cost of a real
     find_endpoint call.

Output is verified identical between OLD and NEW for every query, so the speedup
is a pure performance win (no behaviour change).

Usage:
    python evals/bench_find_endpoint.py [--iterations N]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

import yaml

# Make the package importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dct_mcp_server.config import (  # noqa: E402
    get_available_toolsets,
    load_toolset_grouped_apis,
)
from dct_mcp_server.tools.core.endpoint_discovery import (  # noqa: E402
    build_corpus_from_spec,
    extract_hot_keywords_from_spec,
    get_discovery_index,
    rank_candidates,
)
from dct_mcp_server.tools.core.meta_tools import _endpoint_toolset_index  # noqa: E402

QUERIES = [
    "list all compliance connectors",
    "refresh a vdb by snapshot",
    "provision a new virtual database",
    "delete a bookmark",
    "search for dsources",
    "get engine performance report",
    "roll back a vdb group",
    "create a snapshot of a dsource",
]

LIMIT = 10
MIN_SCORE = 0.15


def _load_cached_spec() -> dict:
    """Load the spec from the dynamic-mode runtime cache.

    Start the server once with DCT_TOOLSET=dynamic to download and cache the
    DCT OpenAPI spec, then re-run this benchmark.
    """
    spec_path = Path(tempfile.gettempdir()) / "dct_mcp_tools" / "api-external-dynamic.yaml"
    if not spec_path.exists():
        raise SystemExit(
            f"Spec not found at {spec_path}. Start the server once in dynamic mode "
            "(DCT_TOOLSET=dynamic) to download and cache the DCT OpenAPI spec, then re-run."
        )
    print(f"Loading spec from {spec_path} ...")
    with open(spec_path) as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------- #
# RANKING layer
# --------------------------------------------------------------------------- #
def rank_old(spec: dict, query: str) -> list:
    """Rebuild corpus + hot keywords on every call (original behaviour)."""
    corpus = build_corpus_from_spec(spec)
    hot = extract_hot_keywords_from_spec(spec)
    return rank_candidates(corpus, query, None, MIN_SCORE, LIMIT, hot)


def rank_new(spec: dict, query: str) -> list:
    """Reuse the cached discovery index (built once)."""
    index = get_discovery_index(spec)
    return rank_candidates(
        index["corpus"], query, None, MIN_SCORE, LIMIT, index["hot_keywords"]
    )


# --------------------------------------------------------------------------- #
# suggested_toolset resolution
# --------------------------------------------------------------------------- #
def _suggested_toolset_old(toolsets: list[str], method: str, path: str) -> str | None:
    """Original per-candidate nested scan over every toolset/tool/api."""
    for ts in toolsets:
        try:
            grouped = load_toolset_grouped_apis(ts)
        except Exception:
            continue
        for tool_info in grouped.values():
            for api in tool_info.get("apis", []):
                if api.get("method") == method and api.get("path") == path:
                    return ts
    return None


def full_old(spec: dict, query: str, toolsets: list[str]) -> list:
    ranked = rank_old(spec, query)
    out = []
    for c in ranked:
        ts = _suggested_toolset_old(toolsets, c["method"], c["path"])
        out.append((c["method"], c["path"], c["score"], ts))
    return out


def full_new(spec: dict, query: str) -> list:
    ranked = rank_new(spec, query)
    idx = _endpoint_toolset_index()
    out = []
    for c in ranked:
        ts = idx.get((c["method"], c["path"]))
        out.append((c["method"], c["path"], c["score"], ts))
    return out


def _strip_rank(ranked: list) -> list:
    return [(c["method"], c["path"], c["score"]) for c in ranked]


def _time(fn, iters: int) -> float:
    t0 = time.perf_counter()
    for _ in range(iters):
        for q in QUERIES:
            fn(q)
    return time.perf_counter() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=50)
    args = ap.parse_args()
    iters = args.iterations

    spec = _load_cached_spec()
    print(f"Spec loaded: {len(spec.get('paths', {}))} paths")
    toolsets = get_available_toolsets()
    print(f"Toolsets scanned by OLD path: {toolsets}\n")

    # ---- correctness ---------------------------------------------------- #
    rank_mismatch = sum(
        _strip_rank(rank_old(spec, q)) != _strip_rank(rank_new(spec, q)) for q in QUERIES
    )
    full_mismatch = sum(full_old(spec, q, toolsets) != full_new(spec, q) for q in QUERIES)
    print(f"Correctness — ranking:   {len(QUERIES) - rank_mismatch}/{len(QUERIES)} identical")
    print(f"Correctness — end-to-end: {len(QUERIES) - full_mismatch}/{len(QUERIES)} identical\n")

    calls = iters * len(QUERIES)

    # Warm caches for NEW (one-time build cost, not per call).
    get_discovery_index(spec)
    _endpoint_toolset_index()

    # ---- ranking layer -------------------------------------------------- #
    r_old = _time(lambda q: rank_old(spec, q), iters)
    r_new = _time(lambda q: rank_new(spec, q), iters)

    # ---- end-to-end ----------------------------------------------------- #
    f_old = _time(lambda q: full_old(spec, q, toolsets), iters)
    f_new = _time(lambda q: full_new(spec, q), iters)

    print(f"Iterations: {iters}  |  Queries/iter: {len(QUERIES)}  |  Total calls: {calls}\n")
    print(f"{'Layer':<14}{'OLD ms/call':>14}{'NEW ms/call':>14}{'Speedup':>12}")
    print("-" * 54)
    print(f"{'ranking':<14}{r_old / calls * 1000:>14.3f}{r_new / calls * 1000:>14.3f}{r_old / r_new:>11.1f}x")
    print(f"{'end-to-end':<14}{f_old / calls * 1000:>14.3f}{f_new / calls * 1000:>14.3f}{f_old / f_new:>11.1f}x")

    return 1 if (rank_mismatch or full_mismatch) else 0


if __name__ == "__main__":
    raise SystemExit(main())
