"""Run the vocabulary translator over a real DCT OpenAPI spec (PPM-1129).

Hand-picked unit examples are not enough for to_canonical(): twice a fix for
the quoted examples left the underlying pattern broken, and the next review
found new false positives simply by running the translator over the real API
text. This module makes that review permanent.

The corpus is every operation summary/description and every schema/property
description in DCT's api-external.yaml (DCT 3.31.0), extracted into
``tests/fixtures/dct_api_text_corpus.json.gz`` (the full 2.8 MB spec is not
committed). To test against a different spec as well, point
``DCT_VOCABULARY_SPEC`` at an api-external.yaml; to refresh the fixture, run::

    python -m tests.unit.test_vocabulary_spec_corpus path/to/api-external.yaml

The assertions are structural invariants that must hold for *any* text, plus a
small set of hand-verified spot checks, so a vocabulary change that reintroduces
the overfitting pattern fails here rather than in front of a customer.
"""

import gzip
import json
import os
import re
import sys
from pathlib import Path

import pytest

from dct_mcp_server.config.loader import load_vocabulary_rules
from dct_mcp_server.tools.core.vocabulary import _translate, to_canonical

_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "dct_api_text_corpus.json.gz"
)


def extract_corpus(spec: dict) -> dict:
    """Every summary/description string in an OpenAPI spec, de-duplicated."""
    operation_text: set = set()
    for item in (spec.get("paths") or {}).values():
        for op in (item or {}).values():
            if isinstance(op, dict):
                for key in ("summary", "description"):
                    value = op.get(key)
                    if isinstance(value, str) and value.strip():
                        operation_text.add(value)

    schema_text: set = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "description" and isinstance(value, str):
                    schema_text.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(spec.get("components") or {})
    return {
        "source": "DCT OpenAPI spec api-external.yaml, info.version "
        + str((spec.get("info") or {}).get("version")),
        "operation_text": sorted(operation_text),
        "schema_text": sorted(schema_text - operation_text),
    }


def _load_corpora() -> list:
    corpora = []
    with gzip.open(_FIXTURE, "rt") as fh:
        corpora.append(json.load(fh))
    live = os.environ.get("DCT_VOCABULARY_SPEC")
    if live:
        import yaml

        with open(live) as fh:
            corpora.append(extract_corpus(yaml.safe_load(fh)))
    return corpora


_CORPORA = _load_corpora()
_TEXTS = sorted({t for c in _CORPORA for t in c["operation_text"] + c["schema_text"]})
# Use _translate directly (S10 / GAP-1): to_canonical() now has an exception
# guard that silently returns the original text on errors, which would mask a
# broken translation rule in the corpus. _translate() raises if something goes
# wrong, so the corpus test will catch actual failures rather than swallowing them.
_PAIRS = [(raw, _translate(raw)) for raw in _TEXTS]
_CHANGED = [(raw, out) for raw, out in _PAIRS if out != raw]


def test_corpus_is_the_real_api_surface():
    assert len(_CORPORA[0]["operation_text"]) > 2000
    assert len(_TEXTS) > 7000
    # Sanity: the corpus really contains the words that went wrong before.
    joined = "\n".join(_TEXTS).lower()
    for word in ("container", "inventory", "delphix engine", "rule set"):
        assert word in joined


# --------------------------------------------------------------------------- #
# Invariants
# --------------------------------------------------------------------------- #

# An immediately repeated run of one to three words ("VDB VDB Groups",
# "VDB Group VDB Group", "rule set rule set").
_REPEAT_RE = re.compile(r"(?<![\w-])(\w+(?:\s+\w+){0,2})\s+\1(?![\w-])", re.I)


def test_translation_never_creates_a_repeated_term():
    offenders = [
        (raw, out)
        for raw, out in _CHANGED
        if len(_REPEAT_RE.findall(out)) > len(_REPEAT_RE.findall(raw))
    ]
    assert not offenders, offenders[:10]


def test_translation_never_nests_a_canonical_term_inside_itself():
    """'the rule set's rule set': a term translated into one already present."""
    offenders = []
    for raw, out in _CHANGED:
        for canonical in {r["canonical"] for r in load_vocabulary_rules()}:
            pattern = rf"{re.escape(canonical)}'s {re.escape(canonical)}"
            if len(re.findall(pattern, out, re.I)) > len(
                re.findall(pattern, raw, re.I)
            ):
                offenders.append((raw, out))
    assert not offenders, offenders[:10]


# Machine identifiers: URLs, POSIX and Windows paths, `code spans`,
# hyphen/dot/@-joined compounds, snake_case and camelCase names.
_IDENTIFIER_RE = re.compile(
    r"https?://\S+"
    r"|`[^`\n]*`"
    # A Title/Title pair such as "Container/Template" is prose, not a path.
    r"|(?<![\w.{}:~%$-])(?![A-Z][a-z]+/[A-Z][a-z]+\b)[\w.{}:~%$-]*[/\\][\w.{}:~%$/\\-]*"
    r"|\w+(?:[-.@]\w+)+"
    r"|\w*_\w+"
    r"|\b[a-z]+[A-Z]\w*"
)


def test_identifiers_survive_byte_for_byte():
    # A hyphenated internal term ("self-service container") is prose, not an
    # identifier: its own words are expected to change.
    internal_terms = [r["internal"].lower() for r in load_vocabulary_rules()]
    offenders = []
    for raw, out in _CHANGED:
        for token in _IDENTIFIER_RE.findall(raw):
            if any(token.lower() in term for term in internal_terms):
                continue
            if token not in out:
                offenders.append((token, raw[:120], out[:120]))
    assert not offenders, offenders[:10]


_SELF_SERVICE_EVIDENCE = re.compile(
    r"(?<![\w-])(self[\s-]*service|jetstream|data[\s-]+(layouts?|templates?)|coordinated)(?![\w-])",
    re.I,
)


def test_bare_container_needs_positive_self_service_evidence():
    """'container' means K8s/Docker, Oracle CDB, Azure blob... unless the text
    itself is about Delphix Self-Service (Jetstream)."""
    offenders = [
        (raw, out)
        for raw, out in _PAIRS
        if not _SELF_SERVICE_EVIDENCE.search(raw)
        and len(re.findall(r"\bcontainers?\b", out, re.I))
        < len(re.findall(r"\bcontainers?\b", raw, re.I))
        - len(re.findall(r"\bdata\s+containers?\b", raw, re.I))
    ]
    assert not offenders, offenders[:10]


def test_inventory_is_never_translated_where_the_text_already_says_rule_set():
    offenders = [
        (raw, out)
        for raw, out in _PAIRS
        if re.search(r"\brule[\s-]?sets?\b", raw, re.I)
        and len(re.findall(r"\binventor(y|ies)\b", out, re.I))
        != len(re.findall(r"\binventor(y|ies)\b", raw, re.I))
    ]
    assert not offenders, offenders[:10]


def test_vdb_inventory_report_is_never_called_a_rule_set():
    for raw, out in _PAIRS:
        if re.search(r"\binventory report", raw, re.I):
            assert re.search(r"\binventory report", out, re.I), (raw, out)


def test_delphix_engine_never_survives_and_names_one_product_only_on_evidence():
    compliance = re.compile(
        r"\b(mask|masks|masked|masking|compliance|profiling)\b", re.I
    )
    data = re.compile(
        r"\b(vdbs?|dsources?|snapshots?|timeflows?|timelines?|virtualization|"
        r"provision\w*|bookmarks?|replication|staging)\b",
        re.I,
    )
    for raw, out in _PAIRS:
        if not re.search(r"\bdelphix engines?\b", raw, re.I):
            continue
        assert not re.search(r"(?<![-/.])\bdelphix engines?\b(?![-/.])", out, re.I), out
        if not compliance.search(raw):
            assert "Continuous Compliance engine" not in out.replace(
                "Continuous Data or Continuous Compliance engine", ""
            ), (raw, out)
        if not data.search(raw):
            assert not re.search(
                r"(?<!or )Continuous Data engine",
                out.replace("Continuous Data or Continuous Compliance engine", ""),
            ), (raw, out)


@pytest.mark.parametrize(
    "term", ["timeflow", "timeflows", "appdata", "toolkit", "mssql"]
)
def test_unambiguous_retired_terms_do_not_survive_in_prose(term):
    """Terms with a single meaning must be translated wherever they are prose."""
    offenders = []
    for raw, out in _PAIRS:
        prose = _IDENTIFIER_RE.sub(" ", out)
        if re.search(rf"\b{term}\b", prose, re.I):
            offenders.append(out[:160])
    assert not offenders, offenders[:10]


# --------------------------------------------------------------------------- #
# Hand-verified spot checks (each read and judged correct by a person)
# --------------------------------------------------------------------------- #

_SPOT_CHECKS = {
    # Unchanged: legitimate non-Delphix "container".
    "The Azure blob container name (AZURE_BLOB_STORAGE mode).": None,
    "The container description of this Linked CDB.": None,
    "Whether the database is running inside a container.": None,
    "Type of the object, either CONTAINER or TEMPLATE.": None,
    # Unchanged: "inventory" as a part of a rule set.
    "Number of data classes in this rule set's inventory that can be re-aligned "
    "to DCT built-ins.": None,
    # Unchanged: Continuous Data report.
    "Search the inventory report for virtualization engine VDBs.": (
        "Search the inventory report for Continuous Data engine VDBs."
    ),
    # Translated: explicit legacy Self-Service term.
    "Source of the vdb group, default is DCT. In case of self-service container, "
    "this value would be ENGINE.": (
        "Source of the VDB Group, default is DCT. In case of VDB Group, "
        "this value would be ENGINE."
    ),
    # Translated: legacy masking usage of "inventory".
    "DataSet information for masking inventory.": (
        "DataSet information for masking rule set."
    ),
    # "Delphix engine" with Continuous Data evidence only.
    "The ingestion strategy configured on the Delphix Engine for this dSource.": (
        "The ingestion strategy configured on the Continuous Data engine for "
        "this dSource."
    ),
    # "Delphix engine" with no evidence: neutral.
    "The ID of the Delphix Engine.": (
        "The ID of the Continuous Data or Continuous Compliance engine."
    ),
    "Virtualization Engine Snapshot of a dSource or VDB.": (
        "Continuous Data engine Snapshot of a dSource or VDB."
    ),
}


@pytest.mark.parametrize("raw,expected", list(_SPOT_CHECKS.items()))
def test_spot_checks(raw, expected):
    if expected is None:
        expected = raw
    assert to_canonical(raw) == expected


def test_spot_check_sources_are_in_the_corpus():
    """The spot checks must be real API text, not invented examples."""
    joined = "\n".join(_CORPORA[0]["operation_text"] + _CORPORA[0]["schema_text"])
    for raw in _SPOT_CHECKS:
        # Tolerate the first-letter case and a trailing period added above.
        probe = raw.rstrip(".")[1:60]
        assert probe in joined, raw


if __name__ == "__main__":  # pragma: no cover - fixture refresh helper
    import yaml

    with open(sys.argv[1]) as fh:
        corpus = extract_corpus(yaml.safe_load(fh))
    with gzip.open(_FIXTURE, "wt", compresslevel=9) as fh:
        json.dump(corpus, fh, indent=0, sort_keys=True)
    print(f"wrote {_FIXTURE} from {corpus['source']}")
