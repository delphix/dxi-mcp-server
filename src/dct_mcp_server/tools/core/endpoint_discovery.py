"""Fuzzy endpoint discovery helpers for auto-mode find_endpoint meta-tool."""

from __future__ import annotations
import re
from difflib import SequenceMatcher
from typing import Any

from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _path_tokens(path: str) -> set[str]:
    no_braces = re.sub(r"\{[^}]+\}", " ", path)
    parts = _PATH_TOKEN_RE.findall(no_braces)
    out: set[str] = set()
    for p in parts:
        out.update(re.findall(r"[a-z]+|[A-Z][a-z]*|[0-9]+", p) or [p])
    return {t.lower() for t in out if t}


def extract_hot_keywords_from_spec(spec: dict[str, Any]) -> frozenset[str]:
    """Derive domain hot-keywords from spec tags and operationId tokens.

    Tags are weighted 3× since they are the spec's canonical resource labels.
    Returns tokens that appear in at least 3 operations (genuinely domain-relevant).
    """
    freq: dict[str, int] = {}
    paths = spec.get("paths", {}) or {}
    for _path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(op, dict):
                continue
            for tag in op.get("tags", []):
                for t in _TOKEN_RE.findall(tag.lower()):
                    freq[t] = freq.get(t, 0) + 3
            op_id = op.get("operationId", "") or ""
            for t in re.findall(r"[a-z]+|[A-Z][a-z]*", op_id):
                freq[t.lower()] = freq.get(t.lower(), 0) + 1
    return frozenset(k for k, v in freq.items() if v >= 3 and len(k) > 2)


def build_corpus_from_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten spec.paths into a list of candidate dicts."""
    out: list[dict[str, Any]] = []
    paths = spec.get("paths", {}) or {}
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(op, dict):
                continue
            out.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": op.get("operationId", "") or "",
                    "summary": op.get("summary", "") or "",
                    "description": op.get("description", "") or "",
                    "tags": op.get("tags", []) or [],
                }
            )
    return out


def _candidate_tokens(candidate: dict[str, Any]) -> frozenset[str]:
    """Merged token set for a candidate (path + summary + operationId + tags).

    This is a pure function of the candidate's static spec fields, so it can be
    computed once at index-build time rather than per query.
    """
    return frozenset(
        _path_tokens(candidate["path"])
        | _tokenize(candidate.get("summary", ""))
        | _tokenize(candidate.get("operation_id", ""))
        | {t.lower() for tag in candidate.get("tags", []) for t in _TOKEN_RE.findall(tag)}
    )


# In-memory discovery index, memoized by spec object identity. The cached spec
# dict is replaced (not mutated) on reload, so id(spec) changing is a reliable
# invalidation signal without wiring into the spec-load path.
_INDEX_CACHE: tuple[int, dict[str, Any]] | None = None


def build_discovery_index(spec: dict[str, Any]) -> dict[str, Any]:
    """Build the derived structures find_endpoint needs, once per spec.

    Returns a dict with:
      - "corpus": list of candidate dicts, each carrying a precomputed
        "tokens" frozenset (so scoring never re-tokenizes).
      - "hot_keywords": frozenset of domain hot-keywords.
    """
    corpus = build_corpus_from_spec(spec)
    for cand in corpus:
        cand["tokens"] = _candidate_tokens(cand)
    return {
        "corpus": corpus,
        "hot_keywords": extract_hot_keywords_from_spec(spec),
    }


def get_discovery_index(spec: dict[str, Any]) -> dict[str, Any]:
    """Return the cached discovery index for *spec*, building it on first use.

    Rebuilds only when a different spec object is passed (e.g. after a reload).
    """
    global _INDEX_CACHE
    if _INDEX_CACHE is not None and _INDEX_CACHE[0] == id(spec):
        return _INDEX_CACHE[1]
    index = build_discovery_index(spec)
    _INDEX_CACHE = (id(spec), index)
    logger.info("Built endpoint discovery index: %d candidates", len(index["corpus"]))
    return index


def score_candidate(
    query_tokens: set[str],
    hot_keywords: frozenset[str],
    candidate: dict[str, Any],
) -> float:
    """Weighted score in [0, 1] combining keyword overlap, path similarity, and hot-keyword boost."""
    if not query_tokens:
        return 0.0
    # Reuse the precomputed token set when the candidate came from the discovery
    # index; fall back to computing it for ad-hoc candidates (back-compat).
    cand_tokens = candidate.get("tokens") or _candidate_tokens(candidate)
    overlap = len(query_tokens & cand_tokens) / max(len(query_tokens), 1)
    ratio = SequenceMatcher(
        None,
        " ".join(sorted(query_tokens)),
        candidate["path"].lower(),
    ).ratio()
    hot_hits = (query_tokens & cand_tokens) & hot_keywords
    hot_boost = min(0.2, 0.05 * len(hot_hits))
    return min(1.0, (0.55 * overlap) + (0.30 * ratio) + hot_boost)


def rank_candidates(
    corpus: list[dict[str, Any]],
    query: str,
    method_types: list[str] | None,
    min_score: float,
    limit: int,
    hot_keywords: frozenset[str],
) -> list[dict[str, Any]]:
    """Return up to `limit` scored candidates sorted by (-score, len(path))."""
    qtokens = _tokenize(query)
    methods_norm = {
        m.upper()
        for m in (method_types or [])
        if m and m.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    }

    def passes_method(c: dict[str, Any]) -> bool:
        if not methods_norm:
            return True
        if c["method"] in methods_norm:
            return True
        # POST /*/search is treated as GET-equivalent when GET is requested
        if "GET" in methods_norm and c["method"] == "POST" and c["path"].endswith("/search"):
            return True
        return False

    scored: list[dict[str, Any]] = []
    for cand in corpus:
        if not passes_method(cand):
            continue
        try:
            s = score_candidate(qtokens, hot_keywords, cand)
        except Exception as exc:
            logger.warning(
                "scoring failed for %s %s: %s", cand.get("method"), cand.get("path"), exc
            )
            continue
        if s >= min_score:
            scored.append({**cand, "score": round(s, 4)})

    scored.sort(key=lambda c: (-c["score"], len(c["path"])))
    return scored[:limit]
