"""
Structured gate decision audit logging.

Emits ``gate_decision`` events to the local application log for every
confirmation gate outcome. Always writes locally regardless of the
``IS_LOCAL_TELEMETRY_ENABLED`` setting — audit trails are mandatory.

Safety rules:
- Never logs: secrets, API keys, HMAC keys, request bodies, or
  ``confirmed_resource_name`` values.
- Only the 7 valid outcomes below are accepted; unknown outcomes are
  logged at WARNING level and the event is still emitted with outcome
  ``"unknown"``.

Valid outcomes:
    required         — gate triggered, awaiting caller confirmation
    approved         — caller supplied valid confirmation; operation proceeding
    refused          — caller refused or gate check failed
    expired          — confirmation token or grant TTL elapsed
    replay_rejected  — token was already consumed (replay attempt)
    grant_covered    — call is covered by an active batch grant
    batch_triggered  — velocity threshold crossed; batch grant issued
"""

import time
from typing import Any

from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

_VALID_OUTCOMES = frozenset(
    {
        "required",
        "approved",
        "refused",
        "expired",
        "replay_rejected",
        "grant_covered",
        "batch_triggered",
    }
)


def emit_gate_event(
    outcome: str,
    identity: str,
    method: str,
    path_template: str,
    level: str,
    *,
    grant_id: str | None = None,
    velocity_fields: dict[str, Any] | None = None,
) -> None:
    """Emit a gate_decision audit event to the local log.

    Always writes locally regardless of IS_LOCAL_TELEMETRY_ENABLED.
    Never includes secrets, request bodies, or confirmed_resource_name.

    Args:
        outcome: One of: required, approved, refused, expired, replay_rejected,
                 grant_covered, batch_triggered
        identity: Caller identity (process UUID or X-CLIENT-ID header value)
        method: HTTP method (POST, DELETE, etc.)
        path_template: URL path template (e.g. "/vdbs/{vdbId}/delete")
        level: Confirmation level applied (standard, elevated, manual, batch_check)
        grant_id: Grant ID if call is grant-covered
        velocity_fields: Dict with threshold_N, window_T, count_at_trigger for
                         batch_triggered events
    """
    if outcome not in _VALID_OUTCOMES:
        logger.warning(
            "audit: unknown gate outcome %r — emitting with outcome='unknown'", outcome
        )
        outcome = "unknown"

    record: dict[str, Any] = {
        "event": "gate_decision",
        "outcome": outcome,
        "caller_identity": identity,
        "method": (method or "").upper(),
        "path_template": path_template,
        "level": level,
        "timestamp": time.time(),
    }

    if grant_id is not None:
        record["grant_id"] = grant_id

    if velocity_fields:
        if "threshold_N" in velocity_fields:
            record["threshold_N"] = velocity_fields["threshold_N"]
        if "window_T" in velocity_fields:
            record["window_T"] = velocity_fields["window_T"]
        if "count_at_trigger" in velocity_fields:
            record["count_at_trigger"] = velocity_fields["count_at_trigger"]

    logger.info(
        "gate_decision outcome=%s identity=%s method=%s path=%s level=%s%s%s",
        record["outcome"],
        record["caller_identity"],
        record["method"],
        record["path_template"],
        record["level"],
        f" grant_id={record['grant_id']}" if grant_id is not None else "",
        (
            f" threshold_N={record.get('threshold_N')}"
            f" window_T={record.get('window_T')}"
            f" count_at_trigger={record.get('count_at_trigger')}"
            if velocity_fields
            else ""
        ),
    )
