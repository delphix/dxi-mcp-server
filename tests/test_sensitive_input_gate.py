"""
Unit tests for the execute() sensitive-input gate (DLPXECO-14406).

Coverage targets:
- _secret_for_identity: username/access_key pairings, prefix handling, non-pairs
- _missing_sensitive_fields: top-level, nested, S3, mutual-exclusion suppression

All functions in this module were AI-generated.
"""

from dct_mcp_server.tools.core.dynamic import (
    _annotated_credential_fields,
    _missing_sensitive_fields,
    _secret_for_identity,
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
        assert _missing_sensitive_fields(
            {"host_parameters": {"username": "u", "password": "p"}}
        ) == []

    def test_s3_access_key_needs_secret_key(self):  # AI-generated
        assert _missing_sensitive_fields({"access_key": "AKIA..."}) == ["secret_key"]

    def test_no_identity_needs_nothing(self):  # AI-generated
        assert _missing_sensitive_fields({"name": "x", "hostname": "h"}) == []

    def test_ssh_key_reference_suppresses_password(self):  # AI-generated
        # ssh_key (a UUID reference) is mutually exclusive with password.
        assert _missing_sensitive_fields(
            {"username": "u", "connection_mode": "SFTP", "ssh_key": "uuid-123"}
        ) == []

    def test_credential_path_id_suppresses_password(self):  # AI-generated
        assert _missing_sensitive_fields(
            {"username": "u", "credential_path_id": "cred-1"}
        ) == []

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
