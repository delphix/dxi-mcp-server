"""
Unit tests for the execute() sensitive-input gate (DLPXECO-14406, DLPXECO-14609).

Coverage targets:
- _secret_for_identity: username/access_key pairings, prefix handling, non-pairs
- _missing_sensitive_fields: top-level, nested, S3, mutual-exclusion suppression
- _verify_host_marker: HMAC verification, body-binding, forgery resistance (DLPXECO-14609)
- Gate second-leg: gate clears after host injects the captured secret (DLPXECO-14609)

All functions in this module were AI-generated.
"""

import hashlib
import hmac as _hmac_mod
import json

from dct_mcp_server.tools.core.dynamic import (
    _annotated_credential_fields,
    _missing_sensitive_fields,
    _secret_for_identity,
    _verify_host_marker,
)


class TestSecretForIdentity:
    def test_username_pairs_with_password(self):  # AI-generated
        assert _secret_for_identity("username") == "password"

    def test_prefixed_username_keeps_prefix(self):  # AI-generated
        assert _secret_for_identity("masking_username") == "masking_password"
        assert _secret_for_identity("source_username") == "source_password"

    def test_user_suffix_pairs_with_password(self):  # AI-generated
        assert _secret_for_identity("db_user") == "db_password"

    def test_access_key_pairs_with_secret_key(self):  # AI-generated
        assert _secret_for_identity("access_key") == "secret_key"

    def test_non_identity_fields_do_not_pair(self):  # AI-generated
        for name in ("hostname", "user_count", "password", "secret_key", "ssh_key"):
            assert _secret_for_identity(name) is None


class TestMissingSensitiveFields:
    def test_top_level_username_needs_password(self):  # AI-generated
        assert _missing_sensitive_fields(
            {"name": "e", "hostname": "h", "username": "admin"}
        ) == ["password"]

    def test_nested_username_needs_password(self):  # AI-generated
        # POST /environments: username nested under host_parameters.
        assert _missing_sensitive_fields(
            {"host_parameters": {"host": "h", "username": "dlpxqa"}}
        ) == ["password"]

    def test_password_already_present_needs_nothing(self):  # AI-generated
        assert (
            _missing_sensitive_fields(
                {"host_parameters": {"username": "u", "password": "p"}}
            )
            == []
        )

    def test_s3_access_key_needs_secret_key(self):  # AI-generated
        assert _missing_sensitive_fields({"access_key": "AKIA..."}) == ["secret_key"]

    def test_no_identity_needs_nothing(self):  # AI-generated
        assert _missing_sensitive_fields({"name": "x", "hostname": "h"}) == []

    def test_ssh_key_reference_suppresses_password(self):  # AI-generated
        # ssh_key (a UUID reference) is mutually exclusive with password.
        assert (
            _missing_sensitive_fields(
                {"username": "u", "connection_mode": "SFTP", "ssh_key": "uuid-123"}
            )
            == []
        )

    def test_credential_path_id_suppresses_password(self):  # AI-generated
        assert (
            _missing_sensitive_fields({"username": "u", "credential_path_id": "cred-1"})
            == []
        )

    def test_empty_body_needs_nothing(self):  # AI-generated
        assert _missing_sensitive_fields(None) == []
        assert _missing_sensitive_fields({}) == []


class TestAnnotatedCredentialFields:  # AI-generated
    """x-dct-toolkit-credential-field is the authoritative secret list."""

    _SPEC = {
        "components": {
            "schemas": {
                "CreateEnv": {
                    "properties": {
                        "username": {"type": "string"},
                        "password": {
                            "type": "string",
                            "x-dct-toolkit-credential-field": True,
                        },
                        "encryption_key": {
                            "type": "string",
                            "x-dct-toolkit-credential-field": True,
                        },
                        "hostname": {"type": "string"},
                        "ssh_key": {
                            "type": "string",
                            "x-dct-toolkit-credential-field": True,
                        },
                    }
                }
            }
        }
    }

    def test_extracts_annotated_names(self):  # AI-generated
        fields = _annotated_credential_fields(self._SPEC)
        assert "password" in fields
        assert "encryption_key" in fields

    def test_excludes_reference_alternatives(self):  # AI-generated
        # ssh_key is a UUID reference, never captured as masked input.
        assert "ssh_key" not in _annotated_credential_fields(self._SPEC)

    def test_unannotated_fields_excluded(self):  # AI-generated
        fields = _annotated_credential_fields(self._SPEC)
        assert "username" not in fields
        assert "hostname" not in fields

    def test_empty_or_missing_spec(self):  # AI-generated
        assert _annotated_credential_fields(None) == frozenset()
        assert _annotated_credential_fields({}) == frozenset()

    def test_standalone_annotated_secret_flagged_inline(self):  # AI-generated
        # encryption_key has no identity to pair with, so only the annotation
        # catches it when the model supplies it inline.
        creds = _annotated_credential_fields(self._SPEC)
        assert _missing_sensitive_fields({"encryption_key": "abc"}, creds) == [
            "encryption_key"
        ]

    def test_annotation_and_pairing_combine(self):  # AI-generated
        creds = _annotated_credential_fields(self._SPEC)
        missing = _missing_sensitive_fields(
            {"username": "u", "encryption_key": "k"}, creds
        )
        assert set(missing) == {"encryption_key", "password"}

    def test_no_credential_set_preserves_pairing_only(self):  # AI-generated
        # Default (empty) set → behaves exactly like the identity-pairing gate.
        assert _missing_sensitive_fields({"encryption_key": "abc"}) == []
        assert _missing_sensitive_fields({"username": "u"}) == ["password"]


# ---------------------------------------------------------------------------
# DLPXECO-14609: Host injection marker — _verify_host_marker
# ---------------------------------------------------------------------------

_SHARED_SECRET = "test-host-secret-key"


def _make_marker(fields: list[str], body: dict | None, secret: str) -> dict:
    """Build a valid host_injection_marker for the given fields and body."""
    payload_dict = {
        "body": json.dumps(body or {}, sort_keys=True, separators=(",", ":")),
        "fields": sorted(fields),
    }
    payload = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))
    hmac_hex = _hmac_mod.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {"fields": fields, "hmac": hmac_hex}


class TestVerifyHostMarker:
    """Unit tests for _verify_host_marker (DLPXECO-14609 AC-1 through AC-6)."""

    def test_valid_marker_returns_cleared_fields(self):
        # AC-1: gate clears for a valid marker.
        body = {"name": "r92t", "username": "dlpxqa", "hostname": "h", "password": "<captured>"}
        marker = _make_marker(["password"], body, _SHARED_SECRET)
        result = _verify_host_marker(marker, body, _SHARED_SECRET)
        assert result == frozenset({"password"})

    def test_no_shared_secret_returns_empty(self):
        # AC-6: with no shared secret configured, no exemptions are granted.
        body = {"username": "u", "password": "p"}
        marker = _make_marker(["password"], body, _SHARED_SECRET)
        # Server has no shared secret → empty frozenset regardless of marker.
        assert _verify_host_marker(marker, body, "") == frozenset()

    def test_none_marker_returns_empty(self):
        assert _verify_host_marker(None, {"password": "p"}, _SHARED_SECRET) == frozenset()

    def test_wrong_hmac_rejected(self):
        # AC-3: model-forged marker without the shared secret is rejected.
        body = {"username": "u", "password": "p"}
        marker = {"fields": ["password"], "hmac": "deadbeef" * 8}
        assert _verify_host_marker(marker, body, _SHARED_SECRET) == frozenset()

    def test_wrong_secret_rejected(self):
        # AC-3: marker signed with a different key is rejected.
        body = {"username": "u", "password": "p"}
        marker = _make_marker(["password"], body, "wrong-secret")
        assert _verify_host_marker(marker, body, _SHARED_SECRET) == frozenset()

    def test_replay_against_different_body_rejected(self):
        # AC-4: marker is body-bound — cannot be replayed with different body.
        body_a = {"username": "u", "password": "secret-a"}
        body_b = {"username": "u", "password": "secret-b"}
        marker = _make_marker(["password"], body_a, _SHARED_SECRET)
        # Same marker presented with body_b must fail.
        assert _verify_host_marker(marker, body_b, _SHARED_SECRET) == frozenset()

    def test_multi_field_marker(self):
        # AC-4: multiple secrets can be cleared in one marker.
        body = {"username": "u", "password": "p", "encryption_key": "k"}
        marker = _make_marker(["password", "encryption_key"], body, _SHARED_SECRET)
        result = _verify_host_marker(marker, body, _SHARED_SECRET)
        assert result == frozenset({"password", "encryption_key"})

    def test_missing_fields_key_rejected(self):
        body = {"password": "p"}
        assert _verify_host_marker({"hmac": "x"}, body, _SHARED_SECRET) == frozenset()

    def test_missing_hmac_key_rejected(self):
        body = {"password": "p"}
        assert _verify_host_marker({"fields": ["password"]}, body, _SHARED_SECRET) == frozenset()

    def test_non_string_field_entries_rejected(self):
        body = {"password": "p"}
        marker = {"fields": [123], "hmac": "anything"}
        assert _verify_host_marker(marker, body, _SHARED_SECRET) == frozenset()


# ---------------------------------------------------------------------------
# DLPXECO-14609: Gate second-leg — _missing_sensitive_fields with host_cleared_fields
# ---------------------------------------------------------------------------

class TestGateSecondLeg:
    """Regression tests for the 'gate loops forever' bug (DLPXECO-14609).

    These tests replicate the exact scenario from the bug report: the gate must
    return no missing fields on the retry leg after the host has injected the secret.
    """

    _SPEC = {
        "components": {
            "schemas": {
                "CreateEnv": {
                    "properties": {
                        "username": {"type": "string"},
                        "password": {
                            "type": "string",
                            "x-dct-toolkit-credential-field": True,
                        },
                    }
                }
            }
        }
    }

    def test_gate_fires_on_first_leg(self):
        # Reproduces the ticket's _missing_sensitive_fields(before, creds) == ['password'].
        creds = _annotated_credential_fields(self._SPEC)
        before = {"name": "r92t", "username": "dlpxqa", "hostname": "r92-tgt.dlpxdc.co", "toolkit_path": "/tmp"}
        assert _missing_sensitive_fields(before, creds) == ["password"]

    def test_gate_loops_without_marker(self):
        # Reproduces the bug: gate returns ['password'] even after password is injected,
        # when no host_cleared_fields exemption is provided.
        creds = _annotated_credential_fields(self._SPEC)
        after = {
            "name": "r92t",
            "username": "dlpxqa",
            "hostname": "r92-tgt.dlpxdc.co",
            "toolkit_path": "/tmp",
            "password": "<captured>",
        }
        # Without marker, rule 1 still fires — the bug.
        assert _missing_sensitive_fields(after, creds) == ["password"]

    def test_gate_clears_on_second_leg_with_valid_marker(self):
        # AC-1: gate clears once the host-injected secret is marked as cleared.
        creds = _annotated_credential_fields(self._SPEC)
        after = {
            "name": "r92t",
            "username": "dlpxqa",
            "hostname": "r92-tgt.dlpxdc.co",
            "toolkit_path": "/tmp",
            "password": "<captured>",
        }
        cleared = frozenset({"password"})
        assert _missing_sensitive_fields(after, creds, cleared) == []

    def test_gate_still_fires_for_uncleared_annotated_field(self):
        # AC-2: rule 1 is not weakened generally — only cleared fields are exempt.
        creds = frozenset({"password", "encryption_key"})
        body = {"username": "u", "password": "p-injected", "encryption_key": "k-model-inline"}
        # Host cleared password but NOT encryption_key.
        cleared = frozenset({"password"})
        missing = _missing_sensitive_fields(body, creds, cleared)
        assert "password" not in missing
        assert "encryption_key" in missing

    def test_identity_pairing_still_enforced_for_absent_secret(self):
        # AC-5: a marker listing a field absent from the body does not suppress
        # the pairing rule — the credential-less call must not be dispatched.
        creds = _annotated_credential_fields(self._SPEC)
        body = {"username": "dlpxqa", "hostname": "h"}  # password absent
        # Marker names "password" but it is NOT in body → pairing rule fires.
        cleared = frozenset({"password"})
        missing = _missing_sensitive_fields(body, creds, cleared)
        assert "password" in missing  # rule 2 (pairing) still fires

    def test_nested_body_clears_after_host_injection(self):
        # AC-4: nested credential field (e.g. host_parameters.password) clears correctly.
        creds = frozenset({"password"})
        body = {"host_parameters": {"username": "u", "password": "<captured>"}}
        cleared = frozenset({"password"})
        assert _missing_sensitive_fields(body, creds, cleared) == []

    def test_no_regression_empty_cleared_set(self):
        # AC-6: empty host_cleared_fields (default) → identical to pre-fix behavior.
        creds = frozenset({"password"})
        body = {"username": "u", "password": "p"}
        # Without cleared fields, rule 1 fires as before.
        assert _missing_sensitive_fields(body, creds) == ["password"]
        assert _missing_sensitive_fields(body, creds, frozenset()) == ["password"]
