"""
Unit tests for the execute() sensitive-input gate (DLPXECO-14406).

Coverage targets:
- _secret_for_identity: username/access_key pairings, prefix handling, non-pairs
- _missing_sensitive_fields: top-level, nested, S3, mutual-exclusion suppression

All functions in this module were AI-generated.
"""

from dct_mcp_server.tools.core.dynamic import (
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
