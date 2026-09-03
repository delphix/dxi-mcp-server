"""Unit tests for host-supplied approval on elevated/manual levels
(DLPXECO-14611).

Kept out of test_sensitive_input_gate.py deliberately: PR #120 (DLPXECO-14609)
also appends to that file, and two PRs appending to the same file conflict on
whichever merges second.

End-to-end coverage of the gate itself lives in
tests/integration/test_host_approval_levels.py.

All functions in this module were AI-generated.
"""


class TestHostApprovalConfirmationLevels:
    """Regression tests for DLPXECO-14611.

    An embedding host with its own trusted approval UI (the DCT AI Assistant's
    Allow once / Allow always buttons) already holds out-of-band evidence of
    human intent. The elevated/manual typed-resource-name checks add nothing
    there -- the *model* would supply that value -- and blocked every delete
    when it supplied the resource name instead of the id.
    """

    @staticmethod
    def _reload_config():
        # get_dct_config reads os.environ at call time; nothing to reset.
        from dct_mcp_server.config.config import get_dct_config

        return get_dct_config()

    def test_DLPXECO14611_flag_defaults_off(self, monkeypatch):  # AI-generated
        monkeypatch.delenv("DCT_CONFIRMATION_HOST_APPROVAL", raising=False)
        assert self._reload_config()["confirmation_host_approval"] is False

    def test_DLPXECO14611_flag_reads_env(self, monkeypatch):  # AI-generated
        monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
        assert self._reload_config()["confirmation_host_approval"] is True
        monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "false")
        assert self._reload_config()["confirmation_host_approval"] is False

    def test_DLPXECO14611_required_fields_drop_typed_id(
        self, monkeypatch
    ):  # AI-generated
        """AC-2: a client must not be asked for fields that are not enforced."""
        from dct_mcp_server.tools.core.confirmation_levels import (
            build_required_fields,
        )

        monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
        assert build_required_fields("manual") == ["confirmation_token"]
        assert build_required_fields("elevated") == ["confirmation_token"]

    def test_DLPXECO14611_required_fields_unchanged_by_default(
        self, monkeypatch
    ):  # AI-generated
        """AC-3: a generic MCP client keeps the full friction."""
        from dct_mcp_server.tools.core.confirmation_levels import (
            build_required_fields,
        )

        monkeypatch.delenv("DCT_CONFIRMATION_HOST_APPROVAL", raising=False)
        assert build_required_fields("elevated") == [
            "confirmation_token",
            "confirmed_resource_name",
        ]
        assert build_required_fields("manual") == [
            "confirmation_token",
            "confirmed_resource_name",
            "acknowledged_impact",
        ]

    def test_DLPXECO14611_validators_still_reject_when_off(
        self, monkeypatch
    ):  # AI-generated
        """The validators themselves are untouched -- only their call sites are
        skipped -- so standalone behaviour cannot silently change."""
        from dct_mcp_server.tools.core.confirmation_levels import (
            validate_elevated,
            validate_manual,
        )

        monkeypatch.delenv("DCT_CONFIRMATION_HOST_APPROVAL", raising=False)
        path = "/environments/2-UNIX_HOST_ENVIRONMENT-9"
        assert validate_elevated(path, "r92-tgt")["ok"] is False
        assert validate_elevated(path, "2-UNIX_HOST_ENVIRONMENT-9")["ok"] is True
        assert validate_manual(path, "2-UNIX_HOST_ENVIRONMENT-9", None)["ok"] is False

    def test_DLPXECO14611_flag_survives_missing_api_key(
        self, monkeypatch
    ):  # AI-generated
        """The flag reads one boolean, so it must not depend on auth config
        being valid. Reading it via require_key=True raises without an API key
        and silently disabled the waiver -- which fails closed, but makes the
        behaviour depend on unrelated configuration."""
        from dct_mcp_server.tools.core.confirmation_levels import (
            build_required_fields,
        )

        monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
        monkeypatch.delenv("DCT_API_KEY", raising=False)
        monkeypatch.setenv("DCT_AUTH_MODE", "standalone")

        assert build_required_fields("manual") == ["confirmation_token"]

    def test_DLPXECO14611_no_stale_resource_name_instruction(self):  # AI-generated
        """No template may instruct the caller to supply confirmed_resource_name.

        Whether that field is required now depends on
        DCT_CONFIRMATION_HOST_APPROVAL, and ``required_fields`` is the
        authoritative channel for it, so the prose must not assert it.

        The ``{name}`` placeholders are deliberately retained -- they are part
        of the message contract a client substitutes for its own users.
        """
        from pathlib import Path

        import dct_mcp_server

        mappings = (
            Path(dct_mcp_server.__file__).parent
            / "config"
            / "mappings"
            / "manual_confirmation.txt"
        ).read_text()
        assert "Provide confirmed_resource_name to proceed" not in mappings
        assert "{name}" in mappings
