"""
Dynamic-mode confirmation resolver for auto mode (DCT_TOOLSET=auto).

In auto/dynamic mode the server exposes the *entire* OpenAPI spec, not just the
hand-curated persona endpoints. The static rule file
``config/mappings/manual_confirmation.txt`` predates that and only covers a
fraction of those endpoints, so it cannot be the source of truth for dynamic
mode.

This module derives the confirmation requirement straight from the spec:

  * DELETE on any path                       -> confirm (manual)
  * POST/PUT/PATCH whose operation summary or
    description contains a "hot" keyword
    (Refresh, Provision, Delete, Rollback,
     Source config, Snapshot)                -> confirm
  * Everything else (incl. all GET reads)    -> pass

GET/HEAD/OPTIONS are treated as non-destructive reads and always pass, even when
their summary mentions a hot keyword (e.g. "Search for snapshots") — otherwise
read/search endpoints would be gated, which is not the intent.

``resolve_confirmation()`` is the single mode-aware entry point: it uses this
spec-derived logic when DCT_TOOLSET=auto and falls back to the static txt rules
for the fixed persona toolsets (preserving their existing behaviour).
"""

from typing import Any, Dict, Optional

from dct_mcp_server.config.config import get_dct_config
from dct_mcp_server.config.loader import get_confirmation_for_operation
from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

# Keywords that mark an impactful/destructive operation when they appear in an
# endpoint's summary or description. Matched case-insensitively as substrings,
# so multi-word phrases like "source config" work.
HOT_CONFIRM_KEYWORDS = (
    "refresh",
    "provision",
    "delete",
    "rollback",
    "source config",
    "snapshot",
)

# Keywords that warrant the strongest (manual) gate vs. a softer (elevated) one.
_MANUAL_KEYWORDS = ("delete",)

_READ_METHODS = {"GET", "HEAD", "OPTIONS"}

_NONE = {"level": "none", "message": None, "conditional": False, "threshold_days": None}


def _none() -> Dict[str, Any]:
    return dict(_NONE)


def _confirm(level: str, message: str) -> Dict[str, Any]:
    return {"level": level, "message": message, "conditional": False, "threshold_days": None}


def _lookup_operation(spec: Dict[str, Any], method: str, path: str) -> Optional[Dict[str, Any]]:
    """Return the OpenAPI operation object for (method, path), or None."""
    if not spec:
        return None
    op = spec.get("paths", {}).get(path, {})
    if not isinstance(op, dict):
        return None
    operation = op.get(method.lower())
    return operation if isinstance(operation, dict) else None


def _matched_keyword(text: str) -> Optional[str]:
    lowered = text.lower()
    for kw in HOT_CONFIRM_KEYWORDS:
        if kw in lowered:
            return kw
    return None


def get_confirmation_for_operation_dynamic(
    method: str,
    path: str,
    spec: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Derive the confirmation requirement for an operation from the spec.

    Returns the same dict shape as
    ``config.loader.get_confirmation_for_operation`` so it is a drop-in
    replacement for the auto-mode call sites.
    """
    method_u = (method or "").upper()

    # Reads never require confirmation.
    if method_u in _READ_METHODS:
        return _none()

    # All deletes require confirmation regardless of description.
    if method_u == "DELETE":
        return _confirm(
            "manual",
            f"This is a destructive DELETE operation on {path}. "
            "Please confirm before proceeding — this action cannot be undone.",
        )

    # Mutating non-delete methods: gate only when a hot keyword is present.
    if spec is None:
        # Lazy import avoids a circular import with tool_factory.
        from .tool_factory import get_cached_spec
        spec = get_cached_spec()

    operation = _lookup_operation(spec, method_u, path) or {}
    text = f"{operation.get('summary', '')} {operation.get('description', '')}".strip()
    keyword = _matched_keyword(text)
    if keyword is None:
        return _none()

    level = "manual" if keyword in _MANUAL_KEYWORDS else "elevated"
    return _confirm(
        level,
        f"This operation may be impactful (matched '{keyword}'): "
        f"{operation.get('summary') or path}. Please review and confirm before proceeding.",
    )


def resolve_confirmation(method: str, path: str) -> Dict[str, Any]:
    """Mode-aware confirmation lookup.

    Auto/dynamic mode derives the requirement from the OpenAPI spec; fixed
    persona toolsets keep using the static ``manual_confirmation.txt`` rules.
    """
    try:
        toolset = get_dct_config().get("toolset", "")
    except Exception:
        toolset = ""

    if toolset == "auto":
        return get_confirmation_for_operation_dynamic(method, path)
    return get_confirmation_for_operation(method, path)
