"""
Unit tests for the execute() sensitive-input gate (DLPXECO-14406).

Coverage targets:
- _missing_sensitive_fields: annotation-driven detection, top-level and nested
- name-based inference is gone -- nothing is a secret unless annotated
  (DLPXECO-14641)
- _host_applied_fields + the second leg of the capture handshake (DLPXECO-14603)

All functions in this module were AI-generated.
"""

from dct_mcp_server.tools.core.dynamic import (
    _SENSITIVE_NONCE_ENV,
    _annotated_credential_fields,
    _host_applied_fields,
    _missing_sensitive_fields,
)


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

    def test_only_annotated_fields_present_are_flagged(self):  # AI-generated
        creds = _annotated_credential_fields(self._SPEC)
        missing = _missing_sensitive_fields(
            {"username": "u", "encryption_key": "k", "password": "p"}, creds
        )
        assert set(missing) == {"encryption_key", "password"}

    def test_no_credential_set_flags_nothing(self):  # AI-generated
        # Without the annotated set there is no other signal, so nothing is
        # flagged -- names alone never make a field a secret.
        assert _missing_sensitive_fields({"encryption_key": "abc"}) == []
        assert _missing_sensitive_fields({"username": "u", "password": "p"}) == []


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
            "password": "model-typed-this",
        }
        after = {**before, "password": "<captured>"}

        # First leg: an annotated secret is in the body, so it is stripped and
        # the host is asked to capture it.
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

    def test_DLPXECO14603_absent_credential_is_not_requested(self):  # AI-generated
        # A body with no annotated credential in it has nothing to strip, so
        # the gate stays silent and the API's own validation decides whether
        # the call is complete. Detecting an *absent* secret required guessing
        # one from `username`, which is exactly the inference DLPXECO-14641
        # removed.
        body = {"username": "dlpxqa"}
        assert _missing_sensitive_fields(body, self._CREDS - _APPLIED) == []
        assert _missing_sensitive_fields(body, self._CREDS) == []


# Identity-shaped fields in the live DCT spec whose suffix-derived "partner"
# does not exist anywhere in the API. The deleted heuristic invented one for
# each of these; all 19 are listed so the regression is pinned by name.
_REFERENCE_IDENTITIES = (
    "environment_user",
    "staging_environment_user",
    "install_user",
    "cluster_user",
    "primary_user",
    "create_user",
    "privileged_os_user",
    "source_host_user",
    "staging_host_user",
    "ppt_host_user",
    "backup_host_user",
    "oracle_fallback_user",
    "vault_username",
    "db_vault_username",
    "ase_db_vault_username",
    "fallback_vault_username",
    "non_sys_vault_username",
    "mssql_user_domain_vault_username",
    "s3_access_key",
)


class TestNoNameBasedInference:
    """Regression tests for DLPXECO-14641 — only the spec's annotation makes a
    field a secret.

    The gate used to derive a partner secret from an identity field's suffix,
    which cannot tell a credential pair from an object reference because DCT
    names both the same way. `environment_user` holds an id (`HOST_USER-18`),
    and the invented `environment_password` exists nowhere in the API, so every
    dSource link and VDB provision stopped for a secret nothing could accept.
    """

    _CREDS = frozenset({"password", "db_password", "secret_key"})

    def test_DLPXECO14641_link_dsource_body_needs_no_secret(self):  # AI-generated
        """The exact reproduction from the ticket."""
        body = {
            "source_id": "2-APPDATA_STAGED_SOURCE_CONFIG-3",
            "name": "R95D115A",
            "link_type": "AppDataStaged",
            "environment_user": "HOST_USER-18",
            "parameters": {"dbName": "R95D115A", "backupPath": "/db2backup/11_5"},
            "sync_parameters": {"resync": True},
        }
        assert _missing_sensitive_fields(body, self._CREDS) == []

    def test_DLPXECO14641_no_reference_identity_invents_a_secret(self):  # AI-generated
        for name in _REFERENCE_IDENTITIES:
            assert _missing_sensitive_fields({name: "REF-1"}, self._CREDS) == [], name

    def test_DLPXECO14641_identity_alone_never_flags(self):  # AI-generated
        # Even a genuine identity field is just a name: with no annotated
        # credential in the body there is nothing to strip.
        for name in ("username", "db_user", "access_key", "masking_username"):
            assert _missing_sensitive_fields({name: "u"}, self._CREDS) == [], name

    def test_DLPXECO14641_annotated_secret_still_flagged(self):  # AI-generated
        # The narrowing must not disable the rule that remains.
        body = {"environment_user": "HOST_USER-18", "db_password": "inline"}
        assert _missing_sensitive_fields(body, self._CREDS) == ["db_password"]

    def test_DLPXECO14641_nested_annotated_secret_still_flagged(self):  # AI-generated
        body = {"name": "x", "host_parameters": {"password": "inline"}}
        assert _missing_sensitive_fields(body, self._CREDS) == ["password"]

    def test_DLPXECO14641_password_alternatives_no_longer_suppress(
        self,
    ):  # AI-generated
        # ssh_key/credential_path_id existed to suppress an *invented* password.
        # With nothing invented they suppress nothing, and an annotated secret
        # sitting beside them is still flagged.
        body = {"username": "u", "ssh_key": "uuid-123", "password": "inline"}
        assert _missing_sensitive_fields(body, self._CREDS) == ["password"]
