"""
Differentiated confirmation level validation (FR-002).

Implements per-level field requirements and validation logic for the
three non-conditional confirmation levels:

  standard  — requires only confirmation_token (no extra checks here)
  elevated  — requires confirmation_token + confirmed_resource_name matching
              the resource ID extracted from the resolved API path
  manual    — all elevated checks plus acknowledged_impact: True

Usage
-----
    from dct_mcp_server.tools.core.confirmation_levels import (
        build_required_fields,
        validate_elevated,
        validate_manual,
    )

Every ``confirmation_required`` response must include a ``required_fields``
key so clients can present the correct fields without parsing message text
(FR-002 AC-6).  Use ``build_required_fields(level)`` to populate it.

EC-7 compliance
---------------
Resource-name comparison uses NFC normalisation (unicodedata.normalize) and
case-folding (str.casefold) so that e.g. ``vdb-RÉSUMÉ-001`` and
``vdb-résumé-001`` are treated as the same resource.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Known action suffixes that appear as the last path segment but are NOT
# resource IDs. The heuristic skips any segment that matches one of these so
# that "/vdbs/vdb-123/refresh_by_timestamp" → "vdb-123", not "refresh_by_timestamp".
# ---------------------------------------------------------------------------
_ACTION_WORDS: frozenset[str] = frozenset(
    {
        "delete",
        "disable",
        "enable",
        "refresh",
        "refresh_by_timestamp",
        "refresh_by_snapshot",
        "refresh_from_bookmark",
        "refresh_by_location",
        "rollback",
        "rollback_by_timestamp",
        "rollback_by_snapshot",
        "rollback_from_bookmark",
        "provision",
        "provision_by_timestamp",
        "provision_by_snapshot",
        "provision_from_bookmark",
        "provision_by_location",
        "snapshots",
        "search",
        "tags",
        "apply",
        "stop",
        "start",
        "restart",
        "unset_expiration",
        "staging-push",
        "oracle",
        "mssql",
        "ase",
        "appdata",
        "empty_vdb",
    }
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def host_approval_configured() -> bool:
    """True when the embedding host presents its own trusted approval UI.

    Read defensively: a config problem must never make a destructive operation
    look *less* gated than it is, so any failure falls back to False.
    """
    try:
        from dct_mcp_server.config.config import get_dct_config

        # require_key=False: this reads one boolean and must not depend on
        # auth config being valid, or the flag silently disables itself
        # wherever DCT_API_KEY is absent.
        conf = get_dct_config(require_key=False)
        return bool(conf.get("confirmation_host_approval", False))
    except Exception:
        return False


def build_required_fields(level: str) -> list[str]:
    """Return the list of extra fields required by a confirmation level.

    Used to populate ``required_fields`` in every ``confirmation_required``
    response so clients don't need to parse message text (FR-002 AC-6).

    Returns:
        standard : ["confirmation_token"]
        elevated : ["confirmation_token", "confirmed_resource_name"]
        manual   : ["confirmation_token", "confirmed_resource_name", "acknowledged_impact"]
        other    : ["confirmation_token"]

    When the host presents its own trusted approval UI, the extra fields are
    not enforced (see validate_elevated / validate_manual call sites), so they
    are not advertised either -- a client must never be asked for a value that
    will be ignored (DLPXECO-14611).
    """
    if host_approval_configured():
        return ["confirmation_token"]
    if level == "elevated":
        return ["confirmation_token", "confirmed_resource_name"]
    if level == "manual":
        return ["confirmation_token", "confirmed_resource_name", "acknowledged_impact"]
    # standard, retention_check, policy_impact_check, or unknown
    return ["confirmation_token"]


def validate_elevated(
    resolved_path: str,
    confirmed_resource_name: str | None,
) -> dict[str, Any]:
    """Validate ``confirmed_resource_name`` for an elevated-level operation.

    Extracts the resource ID from the resolved API path by finding the first
    path segment that is not a collection name (first segment) and not a
    known action word or template placeholder (``{...}``).

    For example:
      "/vdbs/vdb-123/refresh_by_timestamp"  → resource_id = "vdb-123"
      "/vdb-groups/grp-456/rollback"        → resource_id = "grp-456"
      "/vdbs/provision_by_snapshot"         → resource_id = None
                                              (no identifiable resource ID)

    Comparison is case-insensitive using ``str.casefold()`` and
    NFC-normalised via ``unicodedata.normalize("NFC", ...)`` (EC-7).

    Args:
        resolved_path:          Fully-resolved DCT API path, e.g.
                                "/vdbs/vdb-123/refresh_by_timestamp".
        confirmed_resource_name: The value the caller supplied for
                                 ``confirmed_resource_name``, or ``None`` if
                                 the field was omitted.

    Returns:
        dict with keys:
          ok              (bool)       : True if name matches extracted ID.
          resource_id     (str | None) : Extracted resource ID; None if path
                                        does not contain an identifiable ID.
          required_fields (list[str])  : Always the elevated required-fields
                                        list.
          message         (str | None) : Human-readable failure reason; None
                                        when ok is True.
    """
    required = build_required_fields("elevated")
    resource_id = _extract_resource_id(resolved_path)

    if not confirmed_resource_name:
        msg = (
            "confirmed_resource_name is required for elevated operations. "
            f"Please supply the resource ID for the operation on {resolved_path!r}."
        )
        if resource_id:
            msg = (
                f"confirmed_resource_name is required. "
                f"Please type the resource ID '{resource_id}' to confirm this operation."
            )
        logger.debug(
            "elevated validation failed: confirmed_resource_name missing for path=%s",
            resolved_path,
        )
        return {
            "ok": False,
            "resource_id": resource_id,
            "required_fields": required,
            "message": msg,
        }

    if resource_id is None:
        # Cannot extract an ID from the path — accept any non-empty name as
        # a "best-effort" confirmation (fail open toward caution: the caller
        # had to provide *something*).
        logger.debug(
            "elevated validation: no resource_id extractable from path=%s; "
            "accepting non-empty confirmed_resource_name as best-effort",
            resolved_path,
        )
        return {
            "ok": True,
            "resource_id": None,
            "required_fields": required,
            "message": None,
        }

    normalised_input = unicodedata.normalize("NFC", confirmed_resource_name).casefold()
    normalised_id = unicodedata.normalize("NFC", resource_id).casefold()

    if normalised_input != normalised_id:
        logger.debug(
            "elevated validation failed: confirmed_resource_name=%r does not match "
            "resource_id=%r for path=%s",
            confirmed_resource_name,
            resource_id,
            resolved_path,
        )
        return {
            "ok": False,
            "resource_id": resource_id,
            "required_fields": required,
            "message": (
                f"confirmed_resource_name '{confirmed_resource_name}' does not match "
                f"the expected resource ID '{resource_id}'. "
                "Please type the exact resource ID to confirm."
            ),
        }

    return {
        "ok": True,
        "resource_id": resource_id,
        "required_fields": required,
        "message": None,
    }


def validate_manual(
    resolved_path: str,
    confirmed_resource_name: str | None,
    acknowledged_impact: bool | None,
) -> dict[str, Any]:
    """Validate all manual-level confirmation fields.

    Applies all elevated-level checks first (resource name match), then
    verifies that ``acknowledged_impact`` is explicitly ``True``.

    Args:
        resolved_path:          Fully-resolved DCT API path.
        confirmed_resource_name: Caller-supplied resource name (may be None).
        acknowledged_impact:    Caller-supplied impact acknowledgement flag;
                                must be exactly ``True`` to pass.

    Returns:
        dict with keys:
          ok              (bool)       : True only if ALL validations pass.
          resource_id     (str | None) : Extracted resource ID.
          required_fields (list[str])  : Always the manual required-fields list.
          message         (str | None) : Human-readable failure reason for the
                                        first failing check; None when ok is True.
    """
    required = build_required_fields("manual")

    # Run elevated checks first.
    elevated_result = validate_elevated(resolved_path, confirmed_resource_name)
    resource_id = elevated_result["resource_id"]

    if not elevated_result["ok"]:
        # Propagate the elevated failure but upgrade required_fields to manual.
        return {
            "ok": False,
            "resource_id": resource_id,
            "required_fields": required,
            "message": elevated_result["message"],
        }

    # Check acknowledged_impact.
    if acknowledged_impact is not True:
        logger.debug(
            "manual validation failed: acknowledged_impact=%r for path=%s",
            acknowledged_impact,
            resolved_path,
        )
        return {
            "ok": False,
            "resource_id": resource_id,
            "required_fields": required,
            "message": (
                "acknowledged_impact must be set to True to confirm this destructive "
                "operation. Please review the impact and re-submit with "
                "acknowledged_impact=True."
            ),
        }

    return {
        "ok": True,
        "resource_id": resource_id,
        "required_fields": required,
        "message": None,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_resource_id(path: str) -> str | None:
    """Extract the resource ID from a resolved DCT API path.

    Strategy:
      1. Split the path on '/' and discard empty segments.
      2. Skip the first segment — it is the collection name (e.g. "vdbs").
      3. From the remaining segments, return the first one that:
           - Is not a template placeholder (does not start with '{').
           - Does not match a known action word.
      4. Return None if no qualifying segment is found.

    Examples:
      "/vdbs/vdb-123/refresh_by_timestamp"  → "vdb-123"
      "/vdb-groups/grp-456/rollback"        → "grp-456"
      "/dsources/ds-789/delete"             → "ds-789"
      "/vdbs/provision_by_snapshot"         → None  (provision is an action)
      "/vdbs/{vdbId}/delete"                → None  (template placeholder)
    """
    if not path:
        return None

    segments = [s for s in path.split("/") if s]

    if len(segments) < 2:  # Only the collection name; nothing else to check.
        return None

    # Skip segment 0 (collection name), scan the rest.
    for segment in segments[1:]:
        if segment.startswith("{"):
            # Unresolved template placeholder — path was not fully substituted.
            continue
        if segment.lower() in _ACTION_WORDS:
            continue
        # First segment that looks like a real resource ID.
        return segment

    return None
