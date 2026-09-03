"""
Unit tests for the execute() sensitive-input gate (DLPXECO-14406).

Coverage targets:
- _secret_for_identity: username/access_key pairings, prefix handling, non-pairs
- _missing_sensitive_fields: top-level, nested, S3, mutual-exclusion suppression
- _host_applied_fields + the second leg of the capture handshake (DLPXECO-14603)

All functions in this module were AI-generated.
"""

from dct_mcp_server.tools.core.dynamic import (
    _SENSITIVE_NONCE_ENV,
    _annotated_credential_fields,
    _host_applied_fields,
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


class TestHostAppliedFields:
    """Authentication of the host's out-of-band injection marker."""

    _NONCE = "nonce-abc-123"

    def test_DLPXECO14603_valid_marker_returns_fields(
        self, monkeypatch
    ):  # AI-generated
        monkeypatch.setenv(_SENSITIVE_NONCE_ENV, self._NONCE)
        assert _host_applied_fields(
            {"nonce": self._NONCE, "fields": ["password", "secret_key"]}
        ) == frozenset({"password", "secret_key"})

    def test_DLPXECO14603_wrong_nonce_is_ignored(self, monkeypatch):  # AI-generated
        monkeypatch.setenv(_SENSITIVE_NONCE_ENV, self._NONCE)
        assert (
            _host_applied_fields({"nonce": "guessed", "fields": ["password"]})
            == frozenset()
        )

    def test_DLPXECO14603_missing_nonce_is_ignored(self, monkeypatch):  # AI-generated
        monkeypatch.setenv(_SENSITIVE_NONCE_ENV, self._NONCE)
        assert _host_applied_fields({"fields": ["password"]}) == frozenset()

    def test_DLPXECO14603_unset_env_honours_no_marker(
        self, monkeypatch
    ):  # AI-generated
        # Non-embedded deployments have no shared secret, so no caller can
        # ever exempt a field.
        monkeypatch.delenv(_SENSITIVE_NONCE_ENV, raising=False)
        assert (
            _host_applied_fields({"nonce": "", "fields": ["password"]}) == frozenset()
        )

    def test_DLPXECO14603_malformed_marker_is_ignored(
        self, monkeypatch
    ):  # AI-generated
        monkeypatch.setenv(_SENSITIVE_NONCE_ENV, self._NONCE)
        assert _host_applied_fields(None) == frozenset()
        assert _host_applied_fields("password") == frozenset()
        assert (
            _host_applied_fields({"nonce": self._NONCE, "fields": "password"})
            == frozenset()
        )
        assert (
            _host_applied_fields({"nonce": self._NONCE, "fields": [None, ""]})
            == frozenset()
        )


# The host's authenticated marker reaches the gate as a narrowed credential
# set (see the execute() call site), so the tests below narrow it the same way.
_APPLIED = frozenset({"password"})


class TestSensitiveGateSecondLeg:
    """Regression tests for DLPXECO-14603 — the gate must *clear* once the
    host has captured the secret and injected it, or the capture prompt is
    re-issued after every submission and the operation never runs.

    The existing coverage above only asserts the gate fires (first leg).
    """

    _CREDS = frozenset({"password"})

    def test_DLPXECO14603_gate_clears_after_host_injection(self):  # AI-generated
        """Regression test for DLPXECO-14603: password prompt loops forever.

        The exact reproduction from the ticket — identical body before and
        after capture; only the host's marker distinguishes them.
        """
        before = {
            "name": "r92t",
            "username": "dlpxqa",
            "hostname": "r92-tgt.dlpxdc.co",
            "toolkit_path": "/tmp",
        }
        after = {**before, "password": "<captured>"}

        # First leg: the secret is absent, so the host is asked to capture it.
        assert _missing_sensitive_fields(before, self._CREDS) == ["password"]

        # Second leg: the host injected it and says so — the gate must clear.
        assert _missing_sensitive_fields(after, self._CREDS - _APPLIED) == []

    def test_DLPXECO14603_inline_secret_without_marker_still_flagged(
        self,
    ):  # AI-generated
        # A model-supplied inline secret carries no marker, so rule 1 must
        # still fire: the fix must not become "present ⇒ satisfied".
        body = {"username": "dlpxqa", "password": "model-typed-this"}
        assert _missing_sensitive_fields(body, self._CREDS) == ["password"]

    def test_DLPXECO14603_marker_only_exempts_named_fields(self):  # AI-generated
        creds = frozenset({"password", "encryption_key"})
        body = {
            "username": "u",
            "password": "<captured>",
            "encryption_key": "model-typed-this",
        }
        # Only password was captured out-of-band; the inline encryption_key
        # is still flagged.
        assert _missing_sensitive_fields(body, creds - _APPLIED) == ["encryption_key"]

    def test_DLPXECO14603_multi_secret_body_clears(self):  # AI-generated
        creds = frozenset({"password", "secret_key"})
        body = {
            "username": "u",
            "password": "<captured>",
            "access_key": "AKIA...",
            "secret_key": "<captured>",
        }
        applied = frozenset({"password", "secret_key"})
        assert _missing_sensitive_fields(body, creds - applied) == []

    def test_DLPXECO14603_nested_container_clears(self):  # AI-generated
        # POST /environments carries the credential pair inside
        # host_parameters; the secret lands beside its own identity field.
        body = {
            "name": "r92t",
            "host_parameters": {
                "username": "dlpxqa",
                "password": "<captured>",
            },
        }
        assert _missing_sensitive_fields(body, self._CREDS - _APPLIED) == []

    def test_DLPXECO14603_marker_for_absent_field_still_requests_it(
        self,
    ):  # AI-generated
        # The host claims it injected the password but the body has none
        # (injection missed the container). Identity pairing must still ask,
        # rather than dispatching a credential-less call.
        body = {"username": "dlpxqa"}
        assert _missing_sensitive_fields(body, self._CREDS - _APPLIED) == ["password"]
