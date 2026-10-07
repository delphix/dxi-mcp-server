"""Unit tests for the PPM-1129 vocabulary layer.

Covers the instructions loader, the term map, the translator, and the
confirmation-message placeholder renderer.
"""

import pytest

from dct_mcp_server.config.loader import (
    load_server_instructions,
    load_vocabulary_map,
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
    ],
)
def test_to_canonical_translates_and_preserves_case(raw, expected):
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
    ],
)
def test_translation_is_grammatical(raw, expected):
    assert to_canonical(raw) == expected


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
