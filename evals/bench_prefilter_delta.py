#!/usr/bin/env python3
"""
Quantify the speedup AND behavioural delta of a token-overlap prefilter for
find_endpoint's fuzzy ranking.

Background
----------
Profiling shows ~73% of ranking time is difflib.SequenceMatcher.ratio(), called
once per candidate (~988) per query for the 0.30*ratio path-similarity term. A
prefilter would build an inverted index (token -> candidate ids) and only score
candidates that share >=1 token with the query, skipping SequenceMatcher for the
rest.

This is NOT behaviour-neutral. The score is:

    score = 0.55*overlap + 0.30*ratio + hot_boost

A candidate with ZERO token overlap has overlap=0 and hot_boost=0, so its score
is 0.30*ratio. With the default min_score=0.15 it still passes when ratio >= 0.5.
The prefilter drops exactly those candidates. This script measures how often that
actually changes the returned top-N.

Compares, per query:
  * FULL      — current behaviour: score every candidate (rank_candidates).
  * PREFILTER — score only candidates sharing >=1 token with the query.

Reports identical-result rate, the specific dropped endpoints, candidates scored
(SequenceMatcher calls), and the ranking speedup.

Usage:
    python evals/bench_prefilter_delta.py [--iterations N] [--min-score F] [--limit N]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dct_mcp_server.tools.core.endpoint_discovery import (  # noqa: E402
    _tokenize,
    get_discovery_index,
    rank_candidates,
    score_candidate,
)

# Representative intents spanning multiple domains (read, mutate, destructive).
QUERIES = [
    "list all compliance connectors",
    "refresh a vdb by snapshot",
    "provision a new virtual database",
    "delete a bookmark",
    "search for dsources",
    "get engine performance report",
    "roll back a vdb group",
    "create a snapshot of a dsource",
    "register a new engine",
    "update environment configuration",
    "enable a vdb",
    "list api clients",
    "get storage capacity report",
    "add a tag to a dataset",
    "link an oracle dsource",
    "failover a namespace",
    "reset account password",
    "validate file mapping by timestamp",
    "get vdb provisioning defaults",
    "abandon a running job",
]


def _build_inverted_index(corpus: list[dict]) -> dict[str, list[int]]:
    """token -> list of candidate indices that contain it."""
    inv: dict[str, list[int]] = {}
    for i, cand in enumerate(corpus):
        for tok in cand["tokens"]:
            inv.setdefault(tok, []).append(i)
    return inv


def _candidate_subset(corpus, inv, query) -> list[dict]:
    """Candidates sharing >=1 token with the query (prefilter)."""
    qtokens = _tokenize(query)
    idxs: set[int] = set()
    for tok in qtokens:
        idxs.update(inv.get(tok, ()))
    return [corpus[i] for i in idxs]


def rank_prefilter(corpus, inv, query, method_types, min_score, limit, hot) -> list:
    subset = _candidate_subset(corpus, inv, query)
    return rank_candidates(subset, query, method_types, min_score, limit, hot)


def _key(ranked: list) -> list:
    return [(c["method"], c["path"]) for c in ranked]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=30)
    ap.add_argument("--min-score", type=float, default=0.15)
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    spec_path = Path(tempfile.gettempdir()) / "dct_mcp_tools" / "api-external-dynamic.yaml"
    if not spec_path.exists():
        raise SystemExit(
            f"Spec not found at {spec_path}. Start the server once in dynamic mode "
            "(DCT_TOOLSET=dynamic) to download and cache the DCT OpenAPI spec, then re-run."
        )
    print(f"Loading spec from {spec_path} ...")
    spec = yaml.safe_load(open(spec_path))
    index = get_discovery_index(spec)
    corpus, hot = index["corpus"], index["hot_keywords"]
    inv = _build_inverted_index(corpus)
    print(f"Spec: {len(spec.get('paths', {}))} paths  |  {len(corpus)} operations  |  "
          f"{len(inv)} index tokens")
    print(f"min_score={args.min_score}  limit={args.limit}  queries={len(QUERIES)}\n")

    # ---- behavioural delta --------------------------------------------- #
    identical = 0
    total_scored_full = 0
    total_scored_pre = 0
    dropped_rows = 0
    diffs: list[tuple[str, list]] = []

    for q in QUERIES:
        full = rank_candidates(corpus, q, None, args.min_score, args.limit, hot)
        pre = rank_prefilter(corpus, inv, q, None, args.min_score, args.limit, hot)
        total_scored_full += len(corpus)
        total_scored_pre += len(_candidate_subset(corpus, inv, q))

        full_keys, pre_keys = _key(full), _key(pre)
        if full_keys == pre_keys:
            identical += 1
        else:
            # Endpoints present in FULL top-N but missing from PREFILTER top-N.
            pre_set = set(pre_keys)
            lost = [(c["method"], c["path"], c["score"]) for c in full
                    if (c["method"], c["path"]) not in pre_set]
            dropped_rows += len(lost)
            diffs.append((q, lost))

    print("=== Behavioural delta (FULL vs PREFILTER) ===")
    print(f"Queries with identical top-{args.limit}: {identical}/{len(QUERIES)}")
    print(f"Total result rows dropped by prefilter:  {dropped_rows}")
    print(f"Avg candidates scored / query: FULL={total_scored_full // len(QUERIES)}  "
          f"PREFILTER={total_scored_pre // len(QUERIES)}  "
          f"(SequenceMatcher calls reduced ~{total_scored_full / max(total_scored_pre, 1):.0f}x)\n")

    if diffs:
        print("Queries whose results would change:")
        for q, lost in diffs:
            print(f"  - {q!r}")
            for m, p, s in lost:
                print(f"      dropped: {m:6} {p}  (score={s})")
        print()

    # ---- speedup -------------------------------------------------------- #
    iters = args.iterations
    calls = iters * len(QUERIES)

    t0 = time.perf_counter()
    for _ in range(iters):
        for q in QUERIES:
            rank_candidates(corpus, q, None, args.min_score, args.limit, hot)
    full_t = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(iters):
        for q in QUERIES:
            rank_prefilter(corpus, inv, q, None, args.min_score, args.limit, hot)
    pre_t = time.perf_counter() - t0

    print("=== Ranking speedup ===")
    print(f"FULL (score all):       {full_t / calls * 1000:.3f} ms/call")
    print(f"PREFILTER (token gate): {pre_t / calls * 1000:.3f} ms/call")
    print(f"Speedup: {full_t / pre_t:.1f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
