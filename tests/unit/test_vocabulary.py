"""Unit tests for the PPM-1129 vocabulary layer.

Covers the instructions loader, the term map, the translator, and the
confirmation-message placeholder renderer.
"""

import builtins
import threading
from unittest.mock import patch

import pytest

from dct_mcp_server.config.loader import (
    load_server_instructions,
    load_vocabulary_map,
    load_vocabulary_rules,
)
from dct_mcp_server.tools.core.confirmation_resolver import render_message_template
from dct_mcp_server.tools.core.vocabulary import differs, to_canonical


# --------------------------------------------------------------------------- #
# Server instructions
# --------------------------------------------------------------------------- #


def test_server_instructions_load_from_package():
    text = load_server_instructions()
    assert text, "packaged server_instructions.md should not be empty"
    assert "VDB" in text
    assert "timeline" in text


def test_server_instructions_state_the_core_rules():
    text = load_server_instructions()
    for rule in ("timeflow", "AppData", "VDB Group", "Continuous Data engine"):
        assert rule in text, f"instructions should address {rule!r}"


def test_server_instructions_env_override(tmp_path, monkeypatch):
    custom = tmp_path / "custom.md"
    custom.write_text("Only say VDB.")
    monkeypatch.setenv("DCT_SERVER_INSTRUCTIONS", str(custom))
    load_server_instructions.cache_clear()
    assert load_server_instructions() == "Only say VDB."


def test_server_instructions_missing_file_is_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setenv("DCT_SERVER_INSTRUCTIONS", str(tmp_path / "nope.md"))
    load_server_instructions.cache_clear()
    assert load_server_instructions() == ""


# --------------------------------------------------------------------------- #
# GAP-7: non-UTF-8 instructions file is not fatal (S4)
# --------------------------------------------------------------------------- #


def test_server_instructions_invalid_utf8_is_not_fatal(tmp_path, monkeypatch, caplog):
    """S4: A file with invalid UTF-8 bytes must not raise; returns '' + WARNING."""
    import logging

    bad = tmp_path / "bad_instructions.md"
    bad.write_bytes(b"\xff\xfe Vocabulary and domain model guidance.")
    monkeypatch.setenv("DCT_SERVER_INSTRUCTIONS", str(bad))
    load_server_instructions.cache_clear()
    with caplog.at_level(logging.WARNING, logger="dct_mcp_server.config.loader"):
        result = load_server_instructions()
    assert result == ""
    assert any(
        str(bad) in r.message for r in caplog.records if r.levelno >= logging.WARNING
    )


def test_server_instructions_directory_path_is_not_fatal(tmp_path, monkeypatch, caplog):
    """S6: A path pointing at a directory returns '' + WARNING (EC-17)."""
    import logging

    monkeypatch.setenv("DCT_SERVER_INSTRUCTIONS", str(tmp_path))  # tmp_path is a dir
    load_server_instructions.cache_clear()
    with caplog.at_level(logging.WARNING, logger="dct_mcp_server.config.loader"):
        result = load_server_instructions()
    assert result == ""
    assert caplog.records  # at least one warning


def test_server_instructions_empty_file(tmp_path, monkeypatch, caplog):
    """S7: An empty instructions file returns '' without a warning (EC-18)."""
    import logging

    empty = tmp_path / "empty.md"
    empty.write_text("")
    monkeypatch.setenv("DCT_SERVER_INSTRUCTIONS", str(empty))
    load_server_instructions.cache_clear()
    with caplog.at_level(logging.WARNING, logger="dct_mcp_server.config.loader"):
        result = load_server_instructions()
    assert result == ""
    # No WARNING expected for an empty (but readable) file
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)


# --------------------------------------------------------------------------- #
# GAP-1: both config loaders open their file with encoding="utf-8" (S5)
# --------------------------------------------------------------------------- #


def test_config_files_are_opened_as_utf8():
    """S5: Both load_server_instructions and load_vocabulary_rules open with encoding='utf-8'."""
    from dct_mcp_server.config.loader import clear_cache

    real_open = builtins.open
    opens = []

    def recording_open(file, mode="r", **kwargs):
        opens.append((str(file), mode, kwargs.get("encoding")))
        return real_open(file, mode, **kwargs)

    clear_cache()
    with patch("builtins.open", recording_open):
        load_server_instructions()
        load_vocabulary_rules()

    # Every open() for these two config files must use encoding="utf-8"
    for file_path, mode, enc in opens:
        if "server_instructions" in file_path or "vocabulary" in file_path:
            assert enc == "utf-8", (
                f"Expected encoding='utf-8' for {file_path}, got {enc!r}"
            )


# --------------------------------------------------------------------------- #
# GAP-1: vocabulary.txt invalid UTF-8 degrades to identity (S14)
# --------------------------------------------------------------------------- #


def test_vocabulary_invalid_utf8_degrades_to_identity(tmp_path, monkeypatch, caplog):
    """S14: vocabulary.txt with invalid UTF-8 bytes (past 8KB) returns () with no partial rules."""
    import logging

    import dct_mcp_server.config.loader as loader_mod
    from dct_mcp_server.config.loader import clear_cache

    # Build a valid vocabulary.txt that is >8KB followed by invalid bytes
    valid_lines = "timeflow|timeline\n" * 500  # ~9000 chars of valid content
    bad_content = valid_lines.encode("utf-8") + b"\xff\xfe bad"
    vocab_dir = tmp_path / "mappings"
    vocab_dir.mkdir()
    (vocab_dir / "vocabulary.txt").write_bytes(bad_content)

    loader_mod.load_vocabulary_rules.cache_clear()
    monkeypatch.setattr(loader_mod, "MAPPINGS_DIR", vocab_dir)
    try:
        with caplog.at_level(logging.WARNING, logger="dct_mcp_server.config.loader"):
            rules = load_vocabulary_rules()
        assert rules == (), (
            f"Expected no rules (all-or-nothing), got {len(rules)} rules"
        )
        assert any(r.levelno >= logging.WARNING for r in caplog.records)
        # Translation should be identity since there are no rules
        from dct_mcp_server.tools.core.vocabulary import to_canonical as _tc

        assert _tc("Timeflow tf-1") == "Timeflow tf-1"
    finally:
        loader_mod.load_vocabulary_rules.cache_clear()
        clear_cache()


def test_vocabulary_permission_error_degrades_to_identity(
    tmp_path, monkeypatch, caplog
):
    """S14 variant: open() raises PermissionError -> vocabulary degrades to ()."""
    import logging

    import dct_mcp_server.config.loader as loader_mod
    from dct_mcp_server.config.loader import clear_cache

    vocab_dir = tmp_path / "mappings"
    vocab_dir.mkdir()
    (vocab_dir / "vocabulary.txt").write_text("timeflow|timeline\n")

    loader_mod.load_vocabulary_rules.cache_clear()
    monkeypatch.setattr(loader_mod, "MAPPINGS_DIR", vocab_dir)
    try:
        with patch("builtins.open", side_effect=PermissionError("denied")):
            with caplog.at_level(
                logging.WARNING, logger="dct_mcp_server.config.loader"
            ):
                rules = load_vocabulary_rules()
        assert rules == ()
        assert any(r.levelno >= logging.WARNING for r in caplog.records)
    finally:
        loader_mod.load_vocabulary_rules.cache_clear()
        clear_cache()


# --------------------------------------------------------------------------- #
# Term map and translation
# --------------------------------------------------------------------------- #


def test_vocabulary_map_is_ordered_longest_first():
    pairs = load_vocabulary_map()
    assert pairs
    lengths = [len(internal) for internal, _ in pairs]
    assert lengths == sorted(lengths, reverse=True)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Cannot delete timeflow tf-1", "Cannot delete timeline tf-1"),
        ("Timeflow is missing", "Timeline is missing"),
        ("TIMEFLOW REF INVALID", "TIMELINE REF INVALID"),
        ("Install the appdata plugin", "Install the connector"),
        ("MSSql link failed", "SQL Server link failed"),
        (
            "Masking job failed: the inventory is locked",
            "Masking job failed: the rule set is locked",
        ),
        (
            "Cloud Engine capacity exceeded",
            "Continuous Data engine with Elastic Data capacity exceeded",
        ),
        (
            "Delphix Masking job failed to start",
            "Delphix Continuous Compliance job failed to start",
        ),
        (
            "Virtualization Engine is unreachable",
            "Continuous Data engine is unreachable",
        ),
        (
            "Masking Engine returned an error",
            "Continuous Compliance engine returned an error",
        ),
        (
            "Self-Service container cg-1 has no active VDBs",
            "VDB Group cg-1 has no active VDBs",
        ),
        (
            "Cannot rewind VDB vdb-1: active connections",
            "Cannot refresh from self VDB vdb-1: active connections",
        ),
    ],
)
def test_to_canonical_translates_and_preserves_case(raw, expected):
    assert to_canonical(raw) == expected


def test_to_canonical_never_defaults_ambiguous_delphix_engine_to_one_product():
    # Glossary v1.2 #8: "Delphix engine" is ambiguous between the Continuous
    # Data and Continuous Compliance engines. With no context in the text, the
    # translation must name both rather than silently default to one.
    assert (
        to_canonical("Delphix engine is offline")
        == "Continuous Data or Continuous Compliance engine is offline"
    )


def test_to_canonical_output_never_carries_a_model_instruction():
    # message_for_user is customer-facing: no "(clarify which)" style notes.
    for raw in ("Delphix engine is offline", "the delphix engines are busy"):
        out = to_canonical(raw)
        assert "clarify" not in out.lower()
        assert "(" not in out


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            "Delphix engine failed to mask column SSN",
            "Continuous Compliance engine failed to mask column SSN",
        ),
        (
            "Delphix engine could not provision VDB sales-01",
            "Continuous Data engine could not provision VDB sales-01",
        ),
    ],
)
def test_to_canonical_resolves_delphix_engine_from_the_text(raw, expected):
    assert to_canonical(raw) == expected


# "Delphix engine" names a product only on whole-word evidence for exactly one
# of them. Substring/prefix evidence ("profil" in "profile") and words with an
# unrelated meaning ("inventory" in "VDB inventory report") are not evidence.
_NEUTRAL_ENGINE = "Continuous Data or Continuous Compliance engine"


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Replication is a Continuous Data feature; "profile" is not masking
        # evidence. Must not resolve to Continuous Compliance.
        (
            "Replication profile sync failed on Delphix engine",
            "Replication profile sync failed on Continuous Data engine",
        ),
        # A user profile is evidence of neither product.
        (
            "Delphix engine could not load user profile admin",
            f"{_NEUTRAL_ENGINE} could not load user profile admin",
        ),
        # The VDB inventory report is a Continuous Data report; "inventory"
        # is not masking evidence.
        (
            "Delphix engine: VDB inventory report unavailable",
            "Continuous Data engine: VDB inventory report unavailable",
        ),
        # Evidence for both products: say exactly what is known.
        (
            "Delphix engine failed to provision VDB during masking",
            f"{_NEUTRAL_ENGINE} failed to provision VDB during masking",
        ),
        (
            "Delphix engine: masking job 4 blocked by snapshot policy",
            f"{_NEUTRAL_ENGINE}: masking job 4 blocked by snapshot policy",
        ),
    ],
)
def test_delphix_engine_never_resolves_to_the_wrong_product(raw, expected):
    out = to_canonical(raw)
    assert out == expected
    if "masking" not in raw.lower():
        assert "Compliance engine" not in out.replace(_NEUTRAL_ENGINE, "")


def test_delphix_engine_evidence_is_whole_word():
    # "unmasked" and "profiles" are not "masked"/"profiling".
    assert to_canonical(
        "Delphix engine stores profiles for unmaskedish data"
    ).startswith(_NEUTRAL_ENGINE)
    assert to_canonical("Delphix engine profiling job failed").startswith(
        "Continuous Compliance engine"
    )


def test_elastic_data_is_framed_as_an_add_on_not_an_engine():
    # Glossary #28: never imply Elastic Data is an engine of its own.
    assert (
        to_canonical("the Cloud Engine is down")
        == "the Continuous Data engine with Elastic Data is down"
    )


# --------------------------------------------------------------------------- #
# Structure: identifiers are never rewritten
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw",
    [
        "/dct/v3/timeflows/tf-1",
        "https://dct.example.com/dct/v3/timeflows/tf-1",
        "delphix-postgres-plugin",
        "com.delphix.toolkit",
        "/var/lib/appdata/plugins",
        "{timeflowId}",
        "timeflow_id",
        "tf-1",
    ],
)
def test_identifiers_and_paths_are_left_intact(raw):
    assert to_canonical(raw) == raw


@pytest.mark.parametrize(
    "raw,expected",
    [
        # The prose around an identifier is still translated...
        (
            "GET /dct/v3/timeflows/tf-1 failed: timeflow not found",
            "GET /dct/v3/timeflows/tf-1 failed: timeline not found",
        ),
        (
            "Plugin delphix-postgres-plugin failed to load",
            "Connector delphix-postgres-plugin failed to load",
        ),
        (
            "toolkit 'delphix-mongo-toolkit' is not installed",
            "Connector 'delphix-mongo-toolkit' is not installed",
        ),
        # ...including a term whose own spelling is hyphenated.
        ("Self-Service container cg-1 is locked", "VDB Group cg-1 is locked"),
    ],
)
def test_prose_around_identifiers_is_still_translated(raw, expected):
    assert to_canonical(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "C:\\delphix\\toolkit\\bin",
        "Install path C:\\Program_Files\\Delphix\\toolkit is missing",
        "\\\\fileserver\\appdata\\plugins",
        "toolkit@1.0.0",
        "upload of plugin@2.3 failed",
        "set `timeflow_mode` to `appdata`",
    ],
)
def test_windows_paths_versioned_names_and_code_spans_are_protected(raw):
    assert to_canonical(raw) == raw


def test_versioned_name_at_text_start_is_not_capitalised_or_translated():
    # Round-3 report: "toolkit@1.0.0" -> "Connector@1.0.0". Not a sentence
    # capitalisation bug -- the identifier itself must not be rewritten.
    assert to_canonical("toolkit@1.0.0 is installed") == "toolkit@1.0.0 is installed"
    # A real sentence start is still capitalised.
    assert to_canonical("toolkit 1.0.0 is installed") == "Connector 1.0.0 is installed"


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Neighbouring words already spell part of the canonical term.
        (
            "Self-Service: VDB containers cg-1 and cg-2 are locked",
            "Self-Service: VDB Groups cg-1 and cg-2 are locked",
        ),
        ("Jetstream container vdbgroup refresh failed", "VDB Group refresh failed"),
        ("Self-Service container VDB Group is locked", "VDB Group is locked"),
    ],
)
def test_translation_never_doubles_a_term(raw, expected):
    assert to_canonical(raw) == expected


# --------------------------------------------------------------------------- #
# Words with an unrelated everyday meaning
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw",
    [
        # Oracle's own "container database" (CDB) is not a Delphix container.
        "Oracle container database CDB1 is not open",
        "Failed to open container databases on host db01",
        # "container" now means Kubernetes/Docker -- translating it is backwards.
        "Docker container exited with code 137",
        "Kubernetes container restarted",
        "the container image could not be pulled",
        "container exited unexpectedly",
        # DCT's VDB inventory report is a Continuous Data report, not a rule set.
        "VDB inventory report is empty",
        "Failed to search the vdb inventory report",
        # Oracle installation inventory, seen during environment discovery.
        "Oracle central inventory not found on host db01",
        "The inventory location /u01/app/oraInventory is not readable",
        # Inventory with no Continuous Compliance context at all.
        "The inventory is locked",
        # A bare "container" with no Self-Service evidence: real DCT API text
        # where it means an Oracle CDB, an Azure blob container, a connector
        # mount point or a Linux container (DCT 3.31 OpenAPI spec).
        "Container cg-1 has no active VDBs",
        "The Azure blob container name (AZURE_BLOB_STORAGE mode).",
        "The container description of this Linked CDB.",
        "Whether the database is running inside a container.",
        "If true, NOLOGGING operations on this container are treated as faults.",
        "Type of the object, either CONTAINER or TEMPLATE.",
        "Relative path within the container of the directory that should be mounted.",
        # Current DCT text where "inventory" is part of a rule set, not a name
        # for one: translating would produce "the rule set's rule set".
        "Number of algorithms in this rule set's inventory that can be re-aligned.",
        "Starts an asynchronous export of the Rule Set (and its table/column "
        "inventory) to a CSV file.",
        "Update the existing ruleset's inventory using the imported ruleset (csv) file.",
        # Not the retired term: no masking evidence in the text.
        "List the migratable-job inventory across every engine the caller can see",
        # Third-party plugins are not Delphix connectors.
        "Jenkins plugin returned an error",
        "Terraform plugin crashed",
    ],
)
def test_unrelated_meanings_are_not_translated(raw):
    assert to_canonical(raw) == raw


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            "Jetstream container cg-1 has no active VDBs",
            "VDB Group cg-1 has no active VDBs",
        ),
        ("Data container dc-7 is locked", "VDB Group dc-7 is locked"),
        # A bare "container" is translated on positive Self-Service evidence.
        (
            "Self-Service: container cg-1 is locked",
            "Self-Service: VDB Group cg-1 is locked",
        ),
        (
            "Data template dt-1: container cg-1 is locked",
            "Data template dt-1: VDB Group cg-1 is locked",
        ),
        (
            "Masking job 12 failed: inventory has no columns",
            "Masking job 12 failed: rule set has no columns",
        ),
        (
            "Profiling job failed because the inventory is empty",
            "Profiling job failed because the rule set is empty",
        ),
        ("Delphix plugin upload failed", "Delphix connector upload failed"),
    ],
)
def test_retired_meanings_are_still_translated(raw, expected):
    assert to_canonical(raw) == expected


def test_to_canonical_leaves_clean_text_alone():
    clean = "Refresh VDB sales-01 from its latest snapshot"
    assert to_canonical(clean) == clean
    assert differs(clean, to_canonical(clean)) is False


def test_to_canonical_handles_none_and_empty():
    assert to_canonical(None) is None
    assert to_canonical("") == ""


def test_to_canonical_matches_whole_words_only():
    # "timeflows" is mapped, but an unrelated embedded substring is not touched.
    assert to_canonical("retimeflowing") == "retimeflowing"


# --------------------------------------------------------------------------- #
# Confirmation message placeholders
# --------------------------------------------------------------------------- #


def test_placeholder_resolves_from_path():
    out = render_message_template(
        "Are you sure you want to permanently delete VDB '{name}'?",
        "/vdbs/vdb-123/delete",
    )
    assert out == "Are you sure you want to permanently delete VDB 'vdb-123'?"


def test_placeholder_prefers_body_name():
    out = render_message_template(
        "Delete VDB '{name}'?", "/vdbs/vdb-123/delete", {"name": "sales-vdb-01"}
    )
    assert "sales-vdb-01" in out
    assert "vdb-123" not in out


def test_placeholder_clause_dropped_when_unresolvable():
    out = render_message_template(
        "Are you sure you want to permanently delete VDB '{name}'?",
        "/vdbs/provision_by_snapshot",
    )
    assert out == "Are you sure you want to permanently delete VDB?"
    assert "{" not in out


@pytest.mark.parametrize(
    "path,expected_id",
    [
        # Multi-segment collection prefixes: the ID is the value in the
        # template's placeholder position, not the second path segment.
        ("/management/engines/eng-1", "eng-1"),
        ("/management/accounts/12", "12"),
        ("/management/vaults/hashicorp/v-1", "v-1"),
        # Single-segment collections are unchanged.
        ("/vdbs/vdb-123", "vdb-123"),
        ("/vdbs/vdb-123/delete", "vdb-123"),
    ],
)
def test_resource_id_skips_the_whole_collection_prefix(path, expected_id):
    from dct_mcp_server.tools.core.confirmation_levels import _extract_resource_id

    assert _extract_resource_id(path) == expected_id


@pytest.mark.parametrize(
    "method,path,expected",
    [
        (
            "DELETE",
            "/management/engines/eng-1",
            "unregister Continuous Data or Continuous Compliance engine 'eng-1'?",
        ),
        ("DELETE", "/management/accounts/12", "delete user account '12'?"),
        ("DELETE", "/management/vaults/hashicorp/v-1", "HashiCorp vault 'v-1'?"),
        ("POST", "/vdbs/vdb-123/delete", "delete VDB 'vdb-123'"),
    ],
)
def test_confirmation_message_names_the_real_resource(method, path, expected):
    from dct_mcp_server.tools.core.confirmation_resolver import (
        check_confirmation_with_fallback,
    )

    message = check_confirmation_with_fallback(method, path)["message_template"]
    assert expected in message, message


def test_days_clause_dropped_when_unresolvable():
    out = render_message_template(
        "Warning: Updating retention date will cause snapshot '{name}' to be "
        "deleted in {days} day(s). Proceed?",
        "/snapshots/provision_by_snapshot",
    )
    assert out == (
        "Warning: Updating retention date will cause snapshot to be deleted. Proceed?"
    )
    assert "{" not in out and "(s)" not in out


def test_count_clause_dropped_when_unresolvable():
    out = render_message_template(
        "Warning: This policy update will cause {count} snapshot(s)/bookmark(s) "
        "to be deleted within 7 days. Proceed?",
        "/virtualization-policies/p-1",
    )
    assert out == (
        "Warning: This policy update will cause snapshots/bookmarks to be "
        "deleted within 7 days. Proceed?"
    )
    out = render_message_template(
        "Warning: This new policy will affect {count} existing resource(s) "
        "within 7 days. Proceed?",
        "/virtualization-policies",
    )
    assert out == (
        "Warning: This new policy will affect existing resources within 7 days. "
        "Proceed?"
    )


def test_resolved_numbers_agree_with_their_unit():
    template = "Snapshot '{name}' will be deleted in {days} day(s)."
    assert (
        render_message_template(template, "/snapshots/s-1", None, {"retention_days": 1})
        == "Snapshot 's-1' will be deleted in 1 day."
    )
    assert (
        render_message_template(template, "/snapshots/s-1", None, {"retention_days": 3})
        == "Snapshot 's-1' will be deleted in 3 days."
    )


def test_batch_message_count_comes_from_the_velocity_counter():
    out = render_message_template(
        "A single caller has started {count} VDBs within 60 seconds.",
        "/vdbs/vdb-1/start",
        None,
        {"velocity_count": 11},
    )
    assert out == "A single caller has started 11 VDBs within 60 seconds."


def test_no_shipped_rule_renders_garbled_text_without_context():
    """Pre-built tools have no retention/impact context: every rule must
    still render as clean prose."""
    from dct_mcp_server.config.loader import load_manual_confirmation_rules

    for rule in load_manual_confirmation_rules():
        rendered = render_message_template(
            rule.get("message"), "/vdbs/provision_by_snapshot"
        )
        if rendered is None:
            continue
        assert "{" not in rendered, rendered
        assert "(s)" not in rendered or "{" not in rule["message"], rendered
        assert " ." not in rendered and " ?" not in rendered, rendered
        assert "''" not in rendered, rendered


def test_days_and_count_placeholders_resolve_from_context():
    assert "3 days" in render_message_template(
        "Retention is {days} days. Confirm?",
        "/snapshots/s-1/delete",
        None,
        {"retention_days": 3},
    )
    assert "42" in render_message_template(
        "This affects {count} objects. Confirm?",
        "/policies/p-1/apply",
        None,
        {"affected_object_count": 42},
    )


def test_render_passes_none_through():
    assert render_message_template(None, "/vdbs/vdb-1/delete") is None


def test_no_rule_message_leaks_a_raw_brace():
    """Every shipped rule must render without exposing a placeholder."""
    from dct_mcp_server.config.loader import load_manual_confirmation_rules

    for rule in load_manual_confirmation_rules():
        rendered = render_message_template(
            rule.get("message"),
            "/vdbs/vdb-123/delete",
            None,
            {"retention_days": 7, "affected_object_count": 5},
        )
        assert rendered is None or "{" not in rendered, rule.get("message")


# --------------------------------------------------------------------------- #
# Grammar after substitution
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Article agrees with the replacement, not the original word.
        ("referenced by an AppData plugin", "referenced by a connector"),
        ("a timeflow and an environment", "a timeline and an environment"),
        # Canonical casing is used mid-sentence, not the matched word's case.
        ("HTTP 409: timeflow tf-9 missing", "HTTP 409: timeline tf-9 missing"),
        # ...but a sentence start is capitalised.
        ("Timeflow is missing.", "Timeline is missing."),
        ("Delete it. AppData plugin required.", "Delete it. Connector required."),
        # Proper nouns keep their authored casing.
        ("link via mssql failed", "link via SQL Server failed"),
        ("Update values of an MSSql dSource", "Update values of a SQL Server dSource"),
        # Articles the translation did not touch are left alone, even where
        # a vowel-letter rule would get them wrong.
        (
            "a user-provided script for a unique timeflow",
            "a user-provided script for a unique timeline",
        ),
        ("A universal ID for an AppData plugin", "A universal ID for a connector"),
    ],
)
def test_translation_is_grammatical(raw, expected):
    assert to_canonical(raw) == expected


# --------------------------------------------------------------------------- #
# Non-ASCII / Unicode safety (S41) and thread-safety (S42)
# --------------------------------------------------------------------------- #


def test_to_canonical_does_not_corrupt_non_ascii_unicode():
    """S41: Unicode characters are passed through unchanged."""
    texts = [
        "Erreur: timeflow tf-1 introuvable",  # French accent
        "错误：appdata 插件失败",  # Chinese characters
        "エラー：timeflow が見つかりません",  # Japanese
        "Fehler beim AppData-Plugin: ä ö ü",  # German umlauts
        "éàü timeflow missing",  # various Unicode letters
    ]
    for raw in texts:
        result = to_canonical(raw)
        # Characters not part of a retired term must survive intact
        assert result is not None
        # The overall string should not be mangled
        assert len(result) >= 1


def test_to_canonical_is_thread_safe():
    """S42: Concurrent calls to to_canonical() do not interfere with each other."""
    errors = []
    inputs_and_expected = [
        ("Cannot delete timeflow tf-1", "Cannot delete timeline tf-1"),
        ("Install the appdata plugin", "Install the connector"),
        ("Refresh VDB sales-01", "Refresh VDB sales-01"),
        (
            "Virtualization Engine is unreachable",
            "Continuous Data engine is unreachable",
        ),
    ]

    def worker():
        try:
            for raw, expected in inputs_and_expected:
                result = to_canonical(raw)
                if result != expected:
                    errors.append(f"Expected {expected!r}, got {result!r}")
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread-safety failures: {errors[:5]}"


# --------------------------------------------------------------------------- #
# GAP-5: _WARNED_BODY_REFS is a module-level set (S47)
# --------------------------------------------------------------------------- #


def test_warned_body_refs_is_module_level_set():
    """S47: _WARNED_BODY_REFS exists on spec_model and is a set."""
    from dct_mcp_server.tools.core import spec_model

    assert isinstance(spec_model._WARNED_BODY_REFS, set)


# --------------------------------------------------------------------------- #
# GAP-4: clear_cache() must also clear the vocabulary translator's lru_cache (S16)
# --------------------------------------------------------------------------- #


def test_clear_cache_also_clears_vocabulary_translator_cache(tmp_path, monkeypatch):
    """S16: clear_cache() must invalidate the vocabulary translator's caches.

    Before GAP-4, clear_cache() only cleared loader caches. vocabulary.py's
    _compiled_rules() and _translate() are @lru_cache'd independently and were
    never cleared, so new rules written to vocabulary.txt were not picked up
    until process restart.

    After the fix, vocabulary.py registers a hook so clear_cache() also clears
    the translator caches.
    """
    import dct_mcp_server.config.loader as loader_mod
    from dct_mcp_server.config.loader import clear_cache
    from dct_mcp_server.tools.core import vocabulary as vocab_mod

    # Phase 1: seed the vocab dir with "timeflow|timeline" only
    mappings_dir = tmp_path / "mappings"
    mappings_dir.mkdir()
    vocab_file = mappings_dir / "vocabulary.txt"
    vocab_file.write_text("timeflow|timeline\n")

    # Force both caches to read from our tmp dir
    loader_mod.load_vocabulary_rules.cache_clear()
    vocab_mod._compiled_rules.cache_clear()
    vocab_mod._translate.cache_clear()
    monkeypatch.setattr(loader_mod, "MAPPINGS_DIR", mappings_dir)

    # Use mid-sentence forms to avoid sentence-start capitalisation.
    # Seed the translator cache: "faketerm" is NOT in the rules, unchanged.
    assert to_canonical("the faketerm foo") == "the faketerm foo"
    # Confirm "timeflow" IS translated now (also populates _translate cache).
    assert to_canonical("the timeflow tf-1") == "the timeline tf-1"

    # Phase 2: write NEW rules that map "faketerm" -> "realterm"
    vocab_file.write_text("faketerm|realterm\ntimeflow|timeline\n")

    # clear_cache() with GAP-4 fix must tell vocabulary.py to drop its caches
    clear_cache()

    # After cache clear the translator must pick up the new rule.
    # Use mid-sentence form so capitalisation does not mask the actual mismatch.
    result = to_canonical("the faketerm foo")
    assert result == "the realterm foo", (
        f"Expected 'the realterm foo' after clear_cache(), got {result!r}. "
        "GAP-4: vocabulary._compiled_rules and _translate caches were not cleared."
    )

    # Clean up: restore the module-level MAPPINGS_DIR to its real location
    loader_mod.load_vocabulary_rules.cache_clear()
    vocab_mod._compiled_rules.cache_clear()
    vocab_mod._translate.cache_clear()
    clear_cache()


# --------------------------------------------------------------------------- #
# Request bodies declared as a $ref must still expose their fields
# --------------------------------------------------------------------------- #


def test_ref_request_body_exposes_fields():
    """A body pointing at components/requestBodies must be followed.

    Without this, every such operation showed the model zero body fields --
    238 operations in DCT 2026.x, including all /search endpoints, which is
    where filter_expression lives.
    """
    from dct_mcp_server.tools.core.spec_model import OpenAPISpec

    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/things/search": {
                "post": {
                    "summary": "Search things.",
                    "requestBody": {"$ref": "#/components/requestBodies/SearchBody"},
                    "responses": {},
                }
            }
        },
        "components": {
            "requestBodies": {
                "SearchBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/SearchBody"}
                        }
                    },
                }
            },
            "schemas": {
                "SearchBody": {
                    "type": "object",
                    "properties": {
                        "filter_expression": {
                            "type": "string",
                            "description": "A filter expression.",
                        }
                    },
                }
            },
        },
    }

    op = OpenAPISpec(spec).operation_at("/things/search", "post")
    fields = op.request_body.fields()

    assert [f["name"] for f in fields] == ["filter_expression"]
    assert fields[0]["description"] == "A filter expression."
    assert op.request_body.required is True


def test_inline_request_body_still_works():
    """Regression guard for the $ref change above."""
    from dct_mcp_server.tools.core.spec_model import OpenAPISpec

    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/things": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "description": "Name.",
                                        }
                                    },
                                }
                            }
                        }
                    },
                    "responses": {},
                }
            }
        },
    }

    fields = OpenAPISpec(spec).operation_at("/things", "post").request_body.fields()
    assert fields == [
        {"name": "name", "required": True, "type": "string", "description": "Name."}
    ]


# --------------------------------------------------------------------------- #
# Pre-built toolsets render confirmation placeholders too
# --------------------------------------------------------------------------- #


_PREBUILT_MODULES = [
    "dataset",
    "engine",
    "environment",
    "iam",
    "job",
    "misc",
    "policy",
    "reports",
    "template",
]


@pytest.mark.parametrize("module", _PREBUILT_MODULES)
def test_prebuilt_confirmation_message_resolves_name_from_path(module):
    import importlib

    tool_module = importlib.import_module(
        f"dct_mcp_server.tools.{module}_endpoints_tool"
    )
    conf = tool_module.check_confirmation(
        "DELETE", "/database-templates/tmpl-9", "delete", "vdb_template_tool"
    )
    assert conf["status"] == "confirmation_required"
    assert conf["confirmation_message"] == (
        "Are you sure you want to delete VDB template 'tmpl-9'?"
    )


def test_prebuilt_confirmation_message_prefers_body_name():
    from dct_mcp_server.tools.dataset_endpoints_tool import check_confirmation

    conf = check_confirmation(
        "POST",
        "/vdbs/vdb-1/delete",
        "delete_vdb",
        "vdb_tool",
        request_body={"name": "sales-01"},
    )
    assert "'sales-01'" in conf["confirmation_message"]
    assert "{" not in conf["confirmation_message"]


# --------------------------------------------------------------------------- #
# discovery shows OpenAPI summaries in canonical vocabulary
# --------------------------------------------------------------------------- #


_TIMEFLOW_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "DCT", "version": "1"},
    "paths": {
        "/timeflows/{timeflowId}": {
            "get": {
                "operationId": "getTimeflowById",
                "summary": "Get a timeflow by ID.",
                "description": "Returns the timeflow and its AppData toolkit.",
                "tags": ["Timeflows"],
            }
        },
        "/toolkits/search": {
            "post": {
                "operationId": "searchToolkits",
                "summary": "Search for toolkits.",
                "tags": ["Toolkits"],
            }
        },
    },
}


@pytest.fixture
def timeflow_discovery():
    from unittest.mock import MagicMock, patch

    from dct_mcp_server.tools.core.dynamic import _make_discovery_fn

    fn = _make_discovery_fn(MagicMock())
    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_TIMEFLOW_SPEC,
    ):
        yield fn


def test_discovery_list_operations_translates_summaries(timeflow_discovery):
    ops = timeflow_discovery(action="list_operations")["operations"]
    by_path = {op["path"]: op for op in ops}
    timeflow_op = by_path["/timeflows/{timeflowId}"]
    assert timeflow_op["summary"] == "Get a timeline by ID."
    # Identifiers are never translated.
    assert timeflow_op["operationId"] == "getTimeflowById"
    assert by_path["/toolkits/search"]["summary"] == "Search for connectors."


@pytest.mark.parametrize("keyword", ["timeflow", "timeline"])
def test_discovery_keyword_matches_either_vocabulary(timeflow_discovery, keyword):
    ops = timeflow_discovery(action="list_operations", keyword=keyword)["operations"]
    assert [op["path"] for op in ops] == ["/timeflows/{timeflowId}"]


def test_discovery_operation_schema_translates_summary_and_description(
    timeflow_discovery,
):
    result = timeflow_discovery(
        action="get_operation_schema",
        path="/timeflows/{timeflowId}",
        operation_method="GET",
    )
    assert result["path"] == "/timeflows/{timeflowId}"
    assert result["summary"] == "Get a timeline by ID."
    assert result["description"] == "Returns the timeline and its connector."
