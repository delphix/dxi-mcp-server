"""
Confirmation Gate Resolver for the Dynamic 2-Tool Architecture.

Provides a stateless check_confirmation() function that wraps the existing
confirmation rules from config/mappings/manual_confirmation.txt.

Supports standard levels (standard, elevated, manual) and conditional levels:
  retention_check:N   — triggers when context["retention_days"] < N
  policy_impact_check:N — triggers when context["affected_object_count"] > N
"""

from typing import Any

from dct_mcp_server.config.loader import get_confirmation_for_operation
from dct_mcp_server.core.logging import get_logger
from dct_mcp_server.tools.core.confirmation_levels import build_required_fields
from dct_mcp_server.tools.core.velocity_counter import increment_and_check

logger = get_logger(__name__)


def check_confirmation(
    method: str,
    path: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Check whether a DCT API operation requires user confirmation.

    Evaluates the operation against all rules in manual_confirmation.txt (via
    loader.py, which is already @lru_cache'd).  For conditional rule levels
    (retention_check:N, policy_impact_check:N), the supplied *context* dict is
    used to decide whether the trigger threshold is exceeded.

    Args:
        method:  HTTP method string (e.g. "POST", "GET").
        path:    Fully-resolved API path (path params already substituted,
                 e.g. "/vdbs/vdb-123/delete").
        context: Optional extra context for conditional rules.  Recognised keys:
                   - retention_days (int): current snapshot retention in days
                   - affected_object_count (int): number of objects a policy change affects

    Returns:
        dict with keys:
          requires_confirmation (bool)
          confirmation_level    (str | None) — "standard", "elevated", "manual", or None
          message_template      (str | None) — raw message template from the config file
    """
    if context is None:
        context = {}

    raw = get_confirmation_for_operation(method, path)
    level = raw.get("level", "none")
    conditional = raw.get("conditional", False)
    threshold = raw.get("threshold_days")  # int | None

    if level == "none":
        return {
            "requires_confirmation": False,
            "confirmation_level": None,
            "message_template": None,
            "required_fields": [],
        }

    # ------------------------------------------------------------------ #
    # Conditional rule evaluation
    # ------------------------------------------------------------------ #
    if conditional:
        raw_level_str = _reconstruct_level_string(level, threshold, raw)
        if raw_level_str.startswith("retention_check:"):
            threshold_val = _parse_threshold(raw_level_str, "retention_check:")
            retention_days = context.get("retention_days")
            if retention_days is None or int(retention_days) >= threshold_val:
                # Threshold NOT exceeded — no confirmation needed
                return {
                    "requires_confirmation": False,
                    "confirmation_level": None,
                    "message_template": None,
                    "required_fields": [],
                }
            # Threshold exceeded → confirmation required
            return {
                "requires_confirmation": True,
                "confirmation_level": "retention_check",
                "message_template": raw.get("message"),
                "required_fields": build_required_fields("retention_check"),
            }

        if raw_level_str.startswith("policy_impact_check:"):
            threshold_val = _parse_threshold(raw_level_str, "policy_impact_check:")
            affected_count = context.get("affected_object_count")
            if affected_count is None or int(affected_count) <= threshold_val:
                # Threshold NOT exceeded — no confirmation needed
                return {
                    "requires_confirmation": False,
                    "confirmation_level": None,
                    "message_template": None,
                    "required_fields": [],
                }
            return {
                "requires_confirmation": True,
                "confirmation_level": "policy_impact_check",
                "message_template": raw.get("message"),
                "required_fields": build_required_fields("policy_impact_check"),
            }

        # Unknown conditional type — treat as requiring confirmation to be safe
        logger.warning("Unknown conditional confirmation level: %s", raw_level_str)
        return {
            "requires_confirmation": True,
            "confirmation_level": level,
            "message_template": raw.get("message"),
            "required_fields": build_required_fields(level),
        }

    # Standard (non-conditional) match
    return {
        "requires_confirmation": True,
        "confirmation_level": level,
        "message_template": raw.get("message"),
        "required_fields": build_required_fields(level),
    }


def check_confirmation_with_fallback(
    method: str,
    path: str,
    body: dict | None = None,
    identity: str | None = None,
    context: dict | None = None,
) -> dict[str, Any]:
    """
    Check whether a DCT API operation requires user confirmation.

    Extends check_confirmation() with:
    - required_fields in every response (FR-002 AC-6)
    - batch_check level evaluation via velocity counter (FR-006)

    Args:
        method:   HTTP method string (e.g. "POST", "DELETE").
        path:     Fully-resolved API path (path params substituted).
        body:     Request body (used for audit/context, not confirmation logic here).
        identity: Caller identity for velocity counter (X-CLIENT-ID or process UUID).
        context:  Optional extra context for conditional rules.

    Returns:
        dict with keys:
          requires_confirmation (bool)
          confirmation_level    (str | None)
          message_template      (str | None)
          required_fields       (list[str])  — always present
          batch_triggered       (bool)        — True when velocity threshold exceeded
          velocity_count        (int | None)  — current count if batch_check level
          velocity_N            (int | None)  — configured N threshold if batch_check level
          velocity_T            (int | None)  — configured T window (seconds) if batch_check level
    """
    # Step 1: Get base result (already includes required_fields)
    base = check_confirmation(method, path, context)
    level = base.get("confirmation_level")
    requires_confirmation = base["requires_confirmation"]

    # Step 2: Default batch fields
    batch_triggered = False
    velocity_count = None
    velocity_N = None
    velocity_T = None

    # Step 3: Handle batch_check level (FR-006)
    if level == "batch_check":
        raw = get_confirmation_for_operation(method, path)
        N = raw.get("threshold_days") or 5
        T = raw.get("threshold_T") or 3600
        effective_identity = identity or "anonymous"

        triggered, count = increment_and_check(effective_identity, method, path, N, T)
        batch_triggered = triggered
        velocity_count = count
        velocity_N = N
        velocity_T = T
        # Override: only require confirmation when velocity threshold is exceeded
        requires_confirmation = triggered

    return {
        "requires_confirmation": requires_confirmation,
        "confirmation_level": level,
        "message_template": base.get("message_template"),
        "required_fields": base.get(
            "required_fields", build_required_fields(level or "none")
        ),
        "batch_triggered": batch_triggered,
        "velocity_count": velocity_count,
        "velocity_N": velocity_N,
        "velocity_T": velocity_T,
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _reconstruct_level_string(level: str, threshold: int | None, raw: dict) -> str:
    """Re-build the raw level string (e.g. 'retention_check:7') from parsed pieces."""
    if threshold is not None:
        return f"{level}:{threshold}"
    # Fall back to the level string directly (may already be full e.g. 'retention_check:7')
    return level


def _parse_threshold(level_str: str, prefix: str) -> int:
    """Extract the integer threshold from a conditional level string."""
    try:
        return int(level_str[len(prefix) :])
    except (ValueError, IndexError):
        logger.warning("Could not parse threshold from '%s'", level_str)
        return 0
