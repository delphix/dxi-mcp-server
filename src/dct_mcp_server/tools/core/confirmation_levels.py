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


def _known_path_templates() -> list[str]:
    """Every API path template the server's own config knows about.

    The confirmation rules cover every gated operation; the toolset files
    cover the rest of the curated surface. Both loaders are cached.
    """
    from dct_mcp_server.config.loader import (
        get_available_toolsets,
        load_manual_confirmation_rules,
        load_toolset_apis,
    )

    templates = {r["path_pattern"] for r in load_manual_confirmation_rules()}
    for toolset in get_available_toolsets():
        try:
            templates.update(api["path"] for api in load_toolset_apis(toolset))
        except ValueError:
            continue
    return sorted(t for t in templates if t.startswith("/"))


def _split_path(path: str) -> list[str]:
    segments = [s for s in path.split("?")[0].split("/") if s]
    # Tolerate a fully-qualified API path ("/dct/v3/vdbs/vdb-1").
    if segments[:2] == ["dct", "v3"]:
        segments = segments[2:]
    return segments


def _id_from_template(
    segments: list[str], template: str
) -> tuple[int, str | None] | None:
    """Align *segments* with *template*.

    Returns ``(literal_segment_count, value_at_first_placeholder)`` when the
    path matches the template, else None. The value is None when the
    template has no placeholder (a literal collection or action path).
    """
    parts = _split_path(template)
    if len(parts) != len(segments):
        return None
    literal, value = 0, None
    for part, segment in zip(parts, segments):
        if part.startswith("{") and part.endswith("}"):
            if value is None:
                value = segment
        elif part.lower() == segment.lower():
            literal += 1
        else:
            return None
    return literal, value


def _extract_resource_id(path: str, path_template: str | None = None) -> str | None:
    """Extract the resource ID from a resolved DCT API path.

    Structural first: the resolved path is aligned with its API path template
    (the matched confirmation rule's pattern when the caller has it, else the
    most specific template the config knows), and the value in the
    template's first ``{placeholder}`` position is the ID. That is what makes
    multi-segment collection prefixes work:

      "/management/engines/eng-1"            → "eng-1"   (/management/engines/{engineId})
      "/management/accounts/12"              → "12"      (/management/accounts/{id})
      "/management/vaults/hashicorp/v-1"     → "v-1"     (/management/vaults/hashicorp/{vaultId})
      "/vdbs/vdb-123/refresh_by_timestamp"   → "vdb-123"
      "/vdbs/provision_by_snapshot"          → None      (literal template, no ID)

    Only a path no known template matches falls back to the positional
    heuristic: skip the first segment, then return the first segment that is
    neither a ``{placeholder}`` nor a known action word.
    """
    if not path:
        return None

    segments = _split_path(path)
    if not segments:
        return None

    candidates = [path_template] if path_template and "{" in path_template else []
    best: tuple[int, str | None] | None = None
    for template in candidates + _known_path_templates():
        aligned = _id_from_template(segments, template)
        if aligned and (best is None or aligned[0] > best[0]):
            best = aligned
        if aligned and template in candidates:
            # The caller's own matched template is authoritative.
            break
    if best is not None:
        value = best[1]
        if value is None or value.startswith("{") or value.lower() in _ACTION_WORDS:
            return None
        return value

    if len(segments) < 2:  # Only the collection name; nothing else to check.
        return None

    # Fallback heuristic: skip segment 0 (collection name), scan the rest.
    for segment in segments[1:]:
        if segment.startswith("{"):
            # Unresolved template placeholder — path was not fully substituted.
            continue
        if segment.lower() in _ACTION_WORDS:
            continue
        # First segment that looks like a real resource ID.
        return segment

    return None
