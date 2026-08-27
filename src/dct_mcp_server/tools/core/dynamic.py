"""
Dynamic 2-Tool Architecture for DCT MCP Server (DCT_TOOLSET=dynamic).

Registers exactly 2 MCP tools:

  discovery — browse the DCT API surface (list tags, list operations, get schemas)
  execute   — validate, confirm, and dispatch a DCT API call

Both tools read the OpenAPI spec from the spec_cache module-level cache, which is
populated once at startup by main.py via spec_cache.load_and_cache_spec().

This module is independent of the existing tool_factory.py grouped-tool generation.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp import Context
from mcp.types import ClientCapabilities, ElicitationCapability, ToolAnnotations

try:
    from mcp.server.elicitation import (
        AcceptedElicitation,
        DeclinedElicitation,  # noqa: F401
        CancelledElicitation,  # noqa: F401
    )

    _ELICITATION_AVAILABLE = True
except ImportError:
    _ELICITATION_AVAILABLE = False

from pydantic import BaseModel

from dct_mcp_server.config.config import get_dct_config
from dct_mcp_server.core.auth import resolve_auth
from dct_mcp_server.core.client_registry import ClientRegistry
from dct_mcp_server.core.decorators import log_tool_execution
from dct_mcp_server.core.exceptions import DCTClientError
from dct_mcp_server.core.logging import get_logger
from dct_mcp_server.core.session import get_process_identity
from dct_mcp_server.tools.core.audit import emit_gate_event
from dct_mcp_server.tools.core.confirmation_levels import (
    build_required_fields,  # noqa: F401 — available for callers; used by validators
    validate_elevated,
    validate_manual,
)
from dct_mcp_server.tools.core.confirmation_resolver import (
    check_confirmation,
    check_confirmation_with_fallback,
)
from dct_mcp_server.tools.core.confirmation_store import _grant_store
from dct_mcp_server.tools.core.confirmation_token import (
    canonical_json,
    issue_token,
    verify_and_consume_token,
)
from dct_mcp_server.tools.core.floor_operations import is_floor_operation
from dct_mcp_server.tools.core.spec_cache import get_cached_spec
from dct_mcp_server.tools.core.spec_model import OpenAPISpec, RequestBody
from dct_mcp_server.tools.core.velocity_counter import increment_and_check  # noqa: F401

logger = get_logger(__name__)

# Pagination hard cap
_MAX_PAGE_SIZE = 50


# =========================================================================== #
# FR-005: Elicitation Pydantic schemas (primitive fields only per MCP spec)
# =========================================================================== #


class _StandardConfirmationSchema(BaseModel):
    """Elicitation schema for standard confirmation level."""

    confirm: bool


class _ElevatedConfirmationSchema(BaseModel):
    """Elicitation schema for elevated confirmation level."""

    confirm: bool
    confirmed_resource_name: str


class _ManualConfirmationSchema(BaseModel):
    """Elicitation schema for manual confirmation level."""

    confirm: bool
    confirmed_resource_name: str
    acknowledged_impact: bool


def _build_elicitation_schema(level: str | None) -> type[BaseModel]:
    """Return the appropriate elicitation schema class for a confirmation level.

    FR-005 AC-2: elevated requests confirmed_resource_name;
                 manual additionally requests acknowledged_impact.
    """
    if level == "manual":
        return _ManualConfirmationSchema
    if level == "elevated":
        return _ElevatedConfirmationSchema
    return _StandardConfirmationSchema


def _check_elicitation_capability(ctx: Context | None) -> bool:
    """Return True if the connected client declares elicitation capability.

    FR-005: On an elicitation-capable MCP client, the server must obtain
    approval via Context.elicit() rather than returning advisory text.
    """
    if not _ELICITATION_AVAILABLE:
        return False
    if ctx is None:
        return False
    try:
        session = ctx.request_context.session  # type: ignore[union-attr]
        return session.check_client_capability(
            ClientCapabilities(elicitation=ElicitationCapability())
        )
    except Exception:
        return False


# =========================================================================== #
# Public registration entry point
# =========================================================================== #


def register_dynamic_tools(app: FastMCP, dct_client: Any) -> None:
    """
    Register the `discovery` and `execute` tools on the FastMCP app.

    Called by tools/__init__.py when DCT_TOOLSET=dynamic.

    Args:
        app:        FastMCP application instance.
        dct_client: DCTAPIClient instance; captured in execute tool closure.
    """
    logger.info("Registering dynamic 2-tool architecture (discovery + execute)…")

    # We build closures so execute can reference dct_client without globals.
    _discovery_fn = _make_discovery_fn(app)
    _execute_fn = _make_execute_fn(app, dct_client)

    # FR-005 AC-5: Register ToolAnnotations so clients can distinguish
    # read-only (discovery) from destructive (execute).
    _discovery_annotations = ToolAnnotations(readOnlyHint=True)
    _execute_annotations = ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
    )

    app.add_tool(_discovery_fn, name="discovery", annotations=_discovery_annotations)
    logger.info("  Registered: discovery (readOnlyHint=True)")

    app.add_tool(_execute_fn, name="execute", annotations=_execute_annotations)
    logger.info("  Registered: execute (destructiveHint=True)")

    logger.info("Dynamic mode: 2 tools registered (discovery, execute).")


# =========================================================================== #
# Tool factory functions (return decorated callables)
# =========================================================================== #


def _get_spec(app: FastMCP) -> dict[str, Any] | None:
    """Return the OpenAPI spec from the spec_cache module-level cache.

    The spec is populated once at startup by main.py via
    spec_cache.load_and_cache_spec(); discovery/execute read it here.
    """
    return get_cached_spec()


def _get_spec_model(app: FastMCP) -> OpenAPISpec | None:
    """Return the cached spec wrapped in the shared :class:`OpenAPISpec` model.

    All structural traversal ($ref/allOf resolution, path-template matching,
    request-body flattening) flows through this object rather than ad-hoc dict
    walking; see tools/core/spec_model.py.
    """
    return OpenAPISpec.wrap(get_cached_spec())


def _make_discovery_fn(app: FastMCP):
    """Create the discovery tool function as a closure over the app instance."""

    @log_tool_execution
    def discovery(
        action: str,
        tag: str | None = None,
        method: str | None = None,
        keyword: str | None = None,
        path: str | None = None,
        operation_method: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """
        Browse the DCT API surface from the cached OpenAPI spec.

        Actions:
          list_tags            — list all DCT domain tags with operation counts
          list_operations      — list operations with optional tag/method/keyword filters
          get_operation_schema — get fully resolved schema for a specific operation

        Args:
            action:           Required. One of: list_tags, list_operations, get_operation_schema
            tag:              Filter list_operations to a specific OpenAPI tag (e.g. "VDBs")
            method:           Filter list_operations to an HTTP method (GET, POST, PATCH, DELETE, PUT)
            keyword:          Case-insensitive keyword filter on operationId and summary
            path:             Required for get_operation_schema. API path (e.g. "/vdbs/{vdbId}")
            operation_method: Required for get_operation_schema. HTTP method for the path
            page:             Page number for paginated list_operations results (default 1)
            page_size:        Results per page, max 50 (default 20)

        Returns:
            For list_tags: {"tags": [{"name": str, "operation_count": int}]}
            For list_operations: {"operations": [...], "total_count": int, "page": int, "total_pages": int}
            For get_operation_schema: full operation dict with resolved schemas
            On error: {"status": "error", "code": str, "message": str}
        """
        spec = _get_spec(app)
        if not spec:
            return {
                "status": "error",
                "code": "SPEC_NOT_LOADED",
                "message": "OpenAPI spec is not loaded. Server may still be starting up.",
            }

        paths_map: dict[str, Any] = spec.get("paths", {}) or {}

        if action == "list_tags":
            return _action_list_tags(paths_map)

        if action == "list_operations":
            return _action_list_operations(
                paths_map,
                tag_filter=tag,
                method_filter=method.upper() if method else None,
                keyword_filter=keyword,
                page=max(1, page),
                page_size=min(_MAX_PAGE_SIZE, max(1, page_size)),
                spec=spec,
            )

        if action == "get_operation_schema":
            if not path:
                return {
                    "status": "error",
                    "code": "MISSING_PARAMETER",
                    "message": "'path' is required for get_operation_schema",
                }
            if not operation_method:
                return {
                    "status": "error",
                    "code": "MISSING_PARAMETER",
                    "message": "'operation_method' is required for get_operation_schema",
                }
            return _action_get_operation_schema(
                model=OpenAPISpec.wrap(spec),
                path=path,
                operation_method=operation_method.upper(),
            )

        return {
            "status": "error",
            "code": "UNKNOWN_ACTION",
            "message": (
                f"Unknown action '{action}'. "
                "Valid actions: list_tags, list_operations, get_operation_schema"
            ),
        }

    return discovery


def _make_execute_fn(app: FastMCP, dct_client: Any):
    """Create the execute tool function as a closure over app and dct_client."""

    @log_tool_execution
    async def execute(
        path: str,
        method: str,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        confirmed: bool = False,
        confirmation_token: str | None = None,
        confirmed_resource_name: str | None = None,
        acknowledged_impact: bool | None = None,
        batch_intent: dict[str, Any] | None = None,
        grant_token: str | None = None,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """
        Validate, confirm, and dispatch a DCT API call.

        The execute tool acts as a universal DCT API dispatcher.  It:
          1. Substitutes {paramName} placeholders in path using path_params
          2. Looks up the operation in the cached spec (OPERATION_NOT_FOUND if absent)
          3. Validates required parameters against the spec (VALIDATION_ERROR if missing)
          4. Checks confirmation gates for destructive operations (FR-001 through FR-008).
             A destructive op returns confirmation_required (with a confirmation_token)
             until the caller re-calls with that exact token — a bare confirmed=true
             cannot bypass it. Supports batch grants (batch_intent/grant_token) and
             differentiated confirmation levels (standard/elevated/manual).
          5. Dispatches the call via DCTAPIClient

        Args:
            path:         DCT API path, e.g. "/vdbs/{vdbId}/refresh_by_timestamp".
                          Path parameters may be inline ("/vdbs/vdb-123/...") or via path_params.
            method:       HTTP method: GET, POST, PATCH, DELETE, PUT
            path_params:  Key-value map for {paramName} substitution in path
            query_params: Key-value map for query string parameters
            body:         JSON request body
            confirmed:    Deprecated/ignored for destructive operations — a bare
                          confirmed=true no longer bypasses the gate. Use
                          confirmation_token instead.
            confirmation_token: Echo the token returned in a prior
                          confirmation_required response to proceed with a
                          destructive operation (only after explicit user approval).
            confirmed_resource_name: For elevated/manual operations, the resource name
                          or ID of the target as it appears in DCT (e.g. "vdb-123").
                          Required for elevated and manual confirmation levels.
            acknowledged_impact: For manual-level operations, must be set to True to
                          explicitly acknowledge the destructive impact. Required for
                          manual confirmation level.
            batch_intent: Declare a batch grant for N calls. Dict with:
                          - operation (str): "METHOD /path/template"
                          - targets (list): list of canonical bodies or target IDs
                          Returns confirmation_required with a batch_confirmation_token.
            grant_token:  Token from a prior batch_intent confirmation. Pass this on
                          subsequent calls to execute against the active batch grant
                          without requiring individual confirmation for each call.

        Returns:
            On confirmation required: {"status": "confirmation_required", "confirmation_level": str, ...}
            On batch grant issued: {"status": "confirmation_required", "batch_confirmation_token": str, ...}
            On success: {"status": "success", "operation_type": str, "response": dict}
            On validation error: {"status": "error", "code": "VALIDATION_ERROR", "missing_fields": [...]}
            On not found: {"status": "error", "code": "OPERATION_NOT_FOUND", ...}
            On DCT API error: {"status": "error", "code": "DCT_API_ERROR", "http_status": int, ...}
        """
        spec = _get_spec(app)
        if not spec:
            return {
                "status": "error",
                "code": "SPEC_NOT_LOADED",
                "message": "OpenAPI spec is not loaded. Server may still be starting up.",
            }

        method_upper = method.upper()
        model = OpenAPISpec.wrap(spec)

        # ---------------------------------------------------------------- #
        # Step 1 — Resolve path parameters
        # ---------------------------------------------------------------- #
        resolved_path, missing_path_params = _substitute_path_params(
            path, path_params or {}
        )
        if missing_path_params:
            return {
                "status": "error",
                "code": "VALIDATION_ERROR",
                "missing_path_params": missing_path_params,
                "message": (
                    f"Missing required path parameters: {missing_path_params}. "
                    "Provide them via path_params."
                ),
            }

        # ---------------------------------------------------------------- #
        # Step 2 — Look up operation in spec
        # ---------------------------------------------------------------- #
        # Try the resolved path first, then the template path, then without a
        # leading /dct/v3 prefix in case the caller included it.
        path_item = model.find_path_item(resolved_path) or model.find_path_item(path)
        if path_item is None:
            stripped = re.sub(r"^/dct/v3", "", resolved_path)
            path_item = model.find_path_item(stripped)

        if path_item is None:
            return {
                "status": "error",
                "code": "OPERATION_NOT_FOUND",
                "message": (
                    f"Path '{resolved_path}' not found in the cached OpenAPI spec. "
                    "Use discovery(action='list_operations') to browse available endpoints."
                ),
            }

        operation = path_item.get(method_upper.lower())
        if operation is None:
            available_methods = [
                m.upper()
                for m in path_item
                if m.lower() in {"get", "post", "put", "patch", "delete"}
            ]
            return {
                "status": "error",
                "code": "OPERATION_NOT_FOUND",
                "message": (
                    f"Method '{method_upper}' not found for path '{resolved_path}'. "
                    f"Available methods: {available_methods}"
                ),
            }

        # ---------------------------------------------------------------- #
        # Step 3 — Validate required parameters
        # ---------------------------------------------------------------- #
        validation_error = _validate_required_params(
            operation,
            path_params or {},
            query_params or {},
            body,
            resolved_path=resolved_path,
            model=model,
        )
        if validation_error:
            return validation_error

        # ---------------------------------------------------------------- #
        # Step 3.5 — Sensitive-input gate
        # ---------------------------------------------------------------- #
        # Secret-shaped body fields (password/token/…) must never be supplied
        # by the model in `body`. When a mutating operation needs such a field
        # and it is absent, pause so the host can capture it out-of-band (masked
        # input or a stored-credential alias) and re-call with it applied. Runs
        # before the confirmation gate: capture the secret first, then confirm.
        if method_upper in ("POST", "PUT", "PATCH"):
            missing_secrets = _missing_sensitive_fields(
                body, _annotated_credential_fields(spec)
            )
            if missing_secrets:
                return {
                    "status": "sensitive_input_required",
                    "required_sensitive_fields": missing_secrets,
                    "message": (
                        "This operation needs sensitive input: "
                        + ", ".join(missing_secrets)
                    ),
                    "operation": {"path": resolved_path, "method": method_upper},
                    "instructions": (
                        "STOP. Do NOT ask for these secret value(s) in chat and do "
                        "NOT put them in body. The host securely captures them from "
                        "the user (masked input or a stored-credential alias) and "
                        "re-calls execute with them applied automatically. Simply "
                        "wait for the next turn."
                    ),
                }

        # ---------------------------------------------------------------- #
        # Step 4 — Confirmation gate (FR-001 through FR-008)
        # ---------------------------------------------------------------- #
        # Grant-authorization tracking — initialised for every method so the
        # dispatch step can safely annotate grant-covered executions (FR-007).
        _grant_authorized = False
        _grant_remaining: int | None = None
        if method_upper in ("DELETE", "POST", "PUT", "PATCH"):
            # Determine caller identity (FR-006)
            identity = get_process_identity()

            # Load config once
            try:
                _conf = get_dct_config()
                _token_ttl = _conf.get("confirmation_token_ttl", 3600)
                _enforcement = _conf.get("confirmation_enforcement", "advisory")
                _grant_ttl = _conf.get("grant_ttl", 900)
            except Exception:
                _token_ttl = 3600
                _enforcement = "advisory"
                _grant_ttl = 900

            # FR-004: Handle batch_intent (declare a batch grant)
            if batch_intent is not None:
                operation_str = batch_intent.get("operation", "")
                targets = batch_intent.get("targets", [])

                if not targets:
                    return {
                        "status": "error",
                        "code": "INVALID_BATCH",
                        "message": "batch must have at least one target (EC-6)",
                    }

                if len(targets) > 10000:
                    return {
                        "status": "error",
                        "code": "BATCH_TOO_LARGE",
                        "message": "batch_intent.targets exceeds maximum of 10,000 entries",
                    }

                # FR-007: Check floor operations before issuing any grant
                floor_targets = []
                for t in targets:
                    if isinstance(t, dict):
                        # Check if the operation itself is a floor op
                        op_parts = operation_str.split(" ", 1)
                        op_method = op_parts[0].upper() if op_parts else method_upper
                        op_path = op_parts[1] if len(op_parts) > 1 else resolved_path
                        if is_floor_operation(op_method, op_path):
                            floor_targets.append(operation_str)
                            break

                # Also check the resolved path itself
                if is_floor_operation(method_upper, resolved_path):
                    return {
                        "status": "error",
                        "code": "FLOOR_OPERATION_IN_BATCH",
                        "message": (
                            f"Floor operations require individual confirmation and cannot "
                            f"be included in a batch grant: {method_upper} {resolved_path}"
                        ),
                    }

                if floor_targets:
                    return {
                        "status": "error",
                        "code": "FLOOR_OPERATION_IN_BATCH",
                        "message": (
                            f"Floor operations require individual confirmation: {floor_targets}"
                        ),
                    }

                # Issue batch grant
                grant_id = str(uuid.uuid4())[:16]
                canonical_targets = [
                    canonical_json(t) if isinstance(t, dict) else str(t)
                    for t in targets
                ]
                _grant_store.create_grant(
                    grant_id, operation_str, canonical_targets, _grant_ttl
                )

                emit_gate_event(
                    "required", identity, method_upper, resolved_path, "batch_grant"
                )

                targets_display = (
                    canonical_targets[:50]
                    if len(canonical_targets) > 50
                    else canonical_targets
                )
                return {
                    "status": "confirmation_required",
                    "batch_confirmation_token": grant_id,
                    "operation": operation_str,
                    "count": len(targets),
                    "targets_display": targets_display,
                    "message": (
                        f"Batch grant requested for {len(targets)} calls to '{operation_str}'. "
                        "Re-call with grant_token=<batch_confirmation_token> for each operation."
                    ),
                }

            # FR-004: Handle grant_token (execute under an active batch grant)
            if grant_token is not None:
                canonical_body = canonical_json(body)
                consume_result = _grant_store.consume_target(
                    grant_token, canonical_body
                )

                if consume_result == "ok":
                    remaining = _grant_store.get_remaining(grant_token)
                    logger.debug(
                        "Grant %s: target consumed, remaining=%s",
                        grant_token,
                        remaining,
                    )
                    emit_gate_event(
                        "grant_covered",
                        identity,
                        method_upper,
                        resolved_path,
                        "batch_grant",
                        grant_id=grant_token,
                    )
                    # Proceed to execution — grant is valid; skip rest of gate
                    _grant_authorized = True
                    _grant_remaining = remaining
                elif consume_result in ("exhausted", "expired", "grant_missing"):
                    emit_gate_event(
                        "expired",
                        identity,
                        method_upper,
                        resolved_path,
                        "batch_grant",
                        grant_id=grant_token,
                    )
                    new_token = issue_token(
                        method_upper, resolved_path, body, _token_ttl
                    )
                    conf = check_confirmation_with_fallback(
                        method_upper, resolved_path, body, identity
                    )
                    return {
                        "status": "confirmation_required",
                        "confirmation_level": conf.get("confirmation_level"),
                        "message": (
                            f"Batch grant '{grant_token}' is {consume_result}. "
                            "Individual confirmation required."
                        ),
                        "confirmation_token": new_token,
                        "required_fields": conf.get(
                            "required_fields", ["confirmation_token"]
                        ),
                        "ttl_seconds": _token_ttl,
                    }
                else:  # "not_found" — body not in grant
                    emit_gate_event(
                        "required",
                        identity,
                        method_upper,
                        resolved_path,
                        "batch_grant",
                        grant_id=grant_token,
                    )
                    new_token = issue_token(
                        method_upper, resolved_path, body, _token_ttl
                    )
                    conf = check_confirmation_with_fallback(
                        method_upper, resolved_path, body, identity
                    )
                    return {
                        "status": "confirmation_required",
                        "confirmation_level": conf.get("confirmation_level"),
                        "message": (
                            "This call's body is not in the enumerated batch grant. "
                            "Individual confirmation required."
                        ),
                        "confirmation_token": new_token,
                        "required_fields": conf.get(
                            "required_fields", ["confirmation_token"]
                        ),
                        "ttl_seconds": _token_ttl,
                    }
            else:
                _grant_authorized = False

            if not _grant_authorized:
                # Standard per-call confirmation path
                conf = check_confirmation_with_fallback(
                    method_upper, resolved_path, body, identity
                )

                if conf["requires_confirmation"]:
                    conf_level = conf.get("confirmation_level")

                    # Resolve client elicitation capability once — it decides
                    # whether an always-enforced trigger (a velocity/bulk hit)
                    # can be confirmed inline or must be refused outright.
                    has_elicitation = _check_elicitation_capability(ctx)

                    # FR-006/FR-007: Velocity (bulk) detection — always-enforced.
                    if conf.get("batch_triggered"):
                        emit_gate_event(
                            "batch_triggered",
                            identity,
                            method_upper,
                            resolved_path,
                            conf_level or "batch_check",
                            velocity_fields={
                                "threshold_N": conf.get("velocity_N"),
                                "window_T": conf.get("velocity_T"),
                                "count_at_trigger": conf.get("velocity_count"),
                            },
                        )
                        # (b) Targeted hard-block. An advisory confirmation token
                        # is worthless against a runaway automation loop — the
                        # loop would simply echo it back and keep going — so a
                        # client WITHOUT elicitation capability is refused
                        # outright regardless of DCT_CONFIRMATION_ENFORCEMENT.
                        # An elicitation-capable client falls through to
                        # Context.elicit() below for a genuine human decision.
                        if not has_elicitation:
                            emit_gate_event(
                                "refused",
                                identity,
                                method_upper,
                                resolved_path,
                                conf_level or "batch_check",
                            )
                            return {
                                "status": "error",
                                "code": "BULK_OPERATION_BLOCKED",
                                "message": (
                                    (
                                        conf.get("message_template")
                                        or f"Velocity threshold exceeded for {method_upper} {resolved_path}."
                                    )
                                    + f" {conf.get('velocity_count')} call(s) within "
                                    f"{conf.get('velocity_T')}s exceeded the limit of "
                                    f"{conf.get('velocity_N')}. This bulk operation "
                                    "requires human confirmation via an elicitation-capable "
                                    "client and cannot be auto-approved with a token."
                                ),
                                "count": conf.get("velocity_count"),
                                "threshold_N": conf.get("velocity_N"),
                                "window_T": conf.get("velocity_T"),
                            }
                        # Elicitation-capable client: fall through to elicit().

                    # strict + no elicitation → refuse immediately (FR-005 AC-3)
                    if _enforcement == "strict" and not has_elicitation:
                        emit_gate_event(
                            "refused",
                            identity,
                            method_upper,
                            resolved_path,
                            conf_level or "standard",
                        )
                        return {
                            "status": "error",
                            "code": "ELICITATION_REQUIRED",
                            "message": (
                                "Elicitation capability required for destructive operations "
                                f"({method_upper} {resolved_path}) when "
                                "DCT_CONFIRMATION_ENFORCEMENT=strict. "
                                "Client capability: none declared."
                            ),
                        }

                    # Elicitation path (FR-005 AC-1, AC-2, AC-6)
                    if has_elicitation and not confirmation_token:
                        schema_cls = _build_elicitation_schema(conf_level)
                        elicit_message = (
                            conf.get("message_template")
                            or f"This operation ({method_upper} {resolved_path}) requires confirmation."
                        )
                        try:
                            elicit_result = await ctx.elicit(  # type: ignore[union-attr]
                                message=elicit_message,
                                schema=schema_cls,
                            )
                        except Exception as _elicit_err:
                            # ERR-3: elicit raises → return advisory confirmation_required
                            logger.warning(
                                "Context.elicit() raised for %s %s: %s — "
                                "falling back to advisory confirmation_required.",
                                method_upper,
                                resolved_path,
                                _elicit_err,
                            )
                            emit_gate_event(
                                "required",
                                identity,
                                method_upper,
                                resolved_path,
                                conf_level or "standard",
                            )
                            new_token = issue_token(
                                method_upper, resolved_path, body, _token_ttl
                            )
                            return {
                                "status": "confirmation_required",
                                "confirmation_level": conf_level,
                                "message": elicit_message,
                                "confirmation_token": new_token,
                                "required_fields": conf.get(
                                    "required_fields", ["confirmation_token"]
                                ),
                                "ttl_seconds": _token_ttl,
                            }

                        # Process elicitation result
                        if not _ELICITATION_AVAILABLE or not isinstance(
                            elicit_result, AcceptedElicitation
                        ):
                            # Declined or cancelled (FR-005 AC-1)
                            emit_gate_event(
                                "refused",
                                identity,
                                method_upper,
                                resolved_path,
                                conf_level or "standard",
                            )
                            return {
                                "status": "error",
                                "code": "OPERATION_DECLINED",
                                "message": (
                                    f"Operation {method_upper} {resolved_path} was declined "
                                    "by the user via elicitation."
                                ),
                            }

                        # User accepted — extract fields from elicitation data (AC-6)
                        _elicit_data = elicit_result.data
                        if not getattr(_elicit_data, "confirm", True):
                            emit_gate_event(
                                "refused",
                                identity,
                                method_upper,
                                resolved_path,
                                conf_level or "standard",
                            )
                            return {
                                "status": "error",
                                "code": "OPERATION_DECLINED",
                                "message": (
                                    f"Operation {method_upper} {resolved_path} was declined "
                                    "by the user (confirm=false)."
                                ),
                            }

                        # Extract level-specific fields from elicitation response
                        if hasattr(_elicit_data, "confirmed_resource_name"):
                            confirmed_resource_name = (
                                _elicit_data.confirmed_resource_name
                            )
                        if hasattr(_elicit_data, "acknowledged_impact"):
                            acknowledged_impact = _elicit_data.acknowledged_impact

                        # Skip token verification — elicitation approval satisfies the gate
                        # Proceed directly to level-specific checks below.
                        emit_gate_event(
                            "approved",
                            identity,
                            method_upper,
                            resolved_path,
                            conf_level or "standard",
                        )
                        # Fall through to level checks

                    elif not confirmation_token:
                        # No token AND not using elicitation — issue one and return advisory
                        emit_gate_event(
                            "required",
                            identity,
                            method_upper,
                            resolved_path,
                            conf_level or "standard",
                        )
                        new_token = issue_token(
                            method_upper, resolved_path, body, _token_ttl
                        )
                        return {
                            "status": "confirmation_required",
                            "confirmation_level": conf_level,
                            "message": (
                                conf.get("message_template")
                                or f"This operation ({method_upper} {resolved_path}) requires confirmation."
                            ),
                            "confirmation_token": new_token,
                            "required_fields": conf.get(
                                "required_fields", ["confirmation_token"]
                            ),
                            "ttl_seconds": _token_ttl,
                            "operation": {
                                "path": resolved_path,
                                "method": method_upper,
                            },
                            "instructions": (
                                "STOP. Display the message to the user and obtain their EXPLICIT "
                                "approval before proceeding — do NOT approve on their behalf. Once "
                                "the user approves, re-call execute with the IDENTICAL arguments "
                                "plus confirmation_token set to the value above. A bare "
                                "confirmed=true is ignored; the token is required."
                            ),
                        }

                    # Token provided — verify (FR-001: body-bound, single-use)
                    # Skip token verification when elicitation was used (AC-6: token not returned to model)
                    if confirmation_token and not (
                        has_elicitation and not confirmation_token
                    ):
                        if not verify_and_consume_token(
                            confirmation_token,
                            method_upper,
                            resolved_path,
                            body,
                            _token_ttl,
                        ):
                            emit_gate_event(
                                "replay_rejected",
                                identity,
                                method_upper,
                                resolved_path,
                                conf_level or "standard",
                            )
                            new_token = issue_token(
                                method_upper, resolved_path, body, _token_ttl
                            )
                            return {
                                "status": "confirmation_required",
                                "confirmation_level": conf_level,
                                "message": (
                                    "Confirmation token is invalid, expired, or already used. "
                                    "A new token has been issued."
                                ),
                                "confirmation_token": new_token,
                                "required_fields": conf.get(
                                    "required_fields", ["confirmation_token"]
                                ),
                                "ttl_seconds": _token_ttl,
                            }

                    # Token verified (or elicitation-approved) — check level-specific requirements (FR-002)
                    if conf_level == "elevated":
                        level_result = validate_elevated(
                            resolved_path, confirmed_resource_name
                        )
                        if not level_result["ok"]:
                            emit_gate_event(
                                "refused",
                                identity,
                                method_upper,
                                resolved_path,
                                conf_level,
                            )
                            # Re-issue token since we consumed it
                            new_token = issue_token(
                                method_upper, resolved_path, body, _token_ttl
                            )
                            return {
                                "status": "confirmation_required",
                                "confirmation_level": conf_level,
                                "message": (
                                    level_result.get("message")
                                    or "confirmed_resource_name is required for elevated operations."
                                ),
                                "confirmation_token": new_token,
                                "required_fields": level_result.get(
                                    "required_fields",
                                    ["confirmation_token", "confirmed_resource_name"],
                                ),
                                "ttl_seconds": _token_ttl,
                            }

                    elif conf_level == "manual":
                        level_result = validate_manual(
                            resolved_path, confirmed_resource_name, acknowledged_impact
                        )
                        if not level_result["ok"]:
                            emit_gate_event(
                                "refused",
                                identity,
                                method_upper,
                                resolved_path,
                                conf_level,
                            )
                            new_token = issue_token(
                                method_upper, resolved_path, body, _token_ttl
                            )
                            return {
                                "status": "confirmation_required",
                                "confirmation_level": conf_level,
                                "message": (
                                    level_result.get("message")
                                    or "confirmed_resource_name and acknowledged_impact=true are required for manual operations."
                                ),
                                "confirmation_token": new_token,
                                "required_fields": level_result.get(
                                    "required_fields",
                                    [
                                        "confirmation_token",
                                        "confirmed_resource_name",
                                        "acknowledged_impact",
                                    ],
                                ),
                                "ttl_seconds": _token_ttl,
                            }

                    # All checks passed — emit approved event (only if not already emitted via elicitation)
                    if not (has_elicitation and not confirmation_token):
                        emit_gate_event(
                            "approved",
                            identity,
                            method_upper,
                            resolved_path,
                            conf_level or "standard",
                        )

        # ---------------------------------------------------------------- #
        # Step 5 — Annotate operation type
        # ---------------------------------------------------------------- #
        operation_type = _classify_operation_type(method_upper)

        # ---------------------------------------------------------------- #
        # Step 6 — Log warning for GET + body
        # ---------------------------------------------------------------- #
        if method_upper == "GET" and body:
            logger.debug(
                "GET request to %s received a 'body' argument — "
                "GET operations do not use a request body; ignoring body.",
                resolved_path,
            )
            body = None

        # ---------------------------------------------------------------- #
        # Step 7 — Dispatch
        # ---------------------------------------------------------------- #
        try:
            # In embedded mode register_all_tools passes a ClientRegistry; resolve
            # the per-caller DCTAPIClient (keyed by X-CLIENT-ID) before dispatching.
            # In standalone mode dct_client is already a DCTAPIClient.
            client = (
                dct_client.get_client(resolve_auth())
                if isinstance(dct_client, ClientRegistry)
                else dct_client
            )
            response = await client.make_request(
                method=method_upper,
                endpoint=resolved_path,
                params=query_params or None,
                json=body if body is not None else None,
            )
            result = {
                "status": "success",
                "operation_type": operation_type,
                "response": response,
            }
            # FR-007: annotate executions authorized by an active batch grant so
            # the caller can see the grant is being consumed and how much remains.
            if _grant_authorized:
                result["authorization"] = {
                    "grant_token": grant_token,
                    "remaining": _grant_remaining,
                }
            return result
        except DCTClientError as exc:
            http_status = _extract_http_status(str(exc))
            return {
                "status": "error",
                "code": "DCT_API_ERROR",
                "http_status": http_status,
                "message": str(exc),
            }
        except Exception as exc:
            logger.error(
                "Unexpected error dispatching %s %s: %s",
                method_upper,
                resolved_path,
                exc,
            )
            return {
                "status": "error",
                "code": "DCT_API_ERROR",
                "http_status": None,
                "message": str(exc),
            }

    return execute


# =========================================================================== #
# Discovery action implementations
# =========================================================================== #


def _action_list_tags(paths_map: dict[str, Any]) -> dict[str, Any]:
    """Extract all unique tags from spec paths with operation counts."""
    tag_counts: dict[str, int] = {}
    for _path, item in paths_map.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(op, dict):
                continue
            for tag in op.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    tags = [
        {"name": name, "operation_count": count}
        for name, count in sorted(tag_counts.items())
    ]
    return {"tags": tags, "total_count": len(tags)}


def _action_list_operations(
    paths_map: dict[str, Any],
    tag_filter: str | None,
    method_filter: str | None,
    keyword_filter: str | None,
    page: int,
    page_size: int,
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Iterate operations with filters, return paginated results."""
    operations: list[dict[str, Any]] = []

    for path, item in paths_map.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(op, dict):
                continue

            m_upper = method.upper()

            # Method filter
            if method_filter and m_upper != method_filter:
                continue

            # Tag filter
            op_tags = op.get("tags", []) or []
            if tag_filter and tag_filter not in op_tags:
                continue

            # Keyword filter
            op_id = op.get("operationId", "") or ""
            summary = op.get("summary", "") or ""
            if keyword_filter:
                kw = keyword_filter.lower()
                if kw not in op_id.lower() and kw not in summary.lower():
                    continue

            # Confirmation flag
            conf = check_confirmation(m_upper, path)

            operations.append(
                {
                    "method": m_upper,
                    "path": path,
                    "operationId": op_id,
                    "summary": summary,
                    "tags": op_tags,
                    "requires_confirmation": conf["requires_confirmation"],
                }
            )

    # Sort: GET before mutating, then alphabetically by path
    _METHOD_ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}
    operations.sort(key=lambda o: (_METHOD_ORDER.get(o["method"], 9), o["path"]))

    # Paginate
    total_count = len(operations)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = operations[start:end]

    return {
        "operations": page_items,
        "total_count": total_count,
        "page": page,
        "total_pages": total_pages,
    }


def _action_get_operation_schema(
    model: OpenAPISpec | None,
    path: str,
    operation_method: str,
) -> dict[str, Any]:
    """Return the fully-resolved schema for a specific operation.

    All $ref resolution and request-body flattening is delegated to the shared
    :class:`OpenAPISpec` model (tools/core/spec_model.py).
    """
    if model is None:
        return {
            "status": "error",
            "code": "SPEC_NOT_LOADED",
            "message": "OpenAPI spec is not loaded. Server may still be starting up.",
        }

    # Support "POST /vdbs/{vdbId}/delete" format in path argument
    if " " in path:
        parts = path.split(" ", 1)
        operation_method = parts[0].upper()
        path = parts[1].strip()

    path_item = model.find_path_item(path)
    if path_item is None:
        return {
            "status": "error",
            "code": "OPERATION_NOT_FOUND",
            "message": (
                f"Path '{path}' not found in the cached OpenAPI spec. "
                "Use discovery(action='list_tags') or discovery(action='list_operations') to browse."
            ),
        }

    if path_item.get(operation_method.lower()) is None:
        available = [
            m.upper()
            for m in path_item
            if m.lower() in {"get", "post", "put", "patch", "delete"}
        ]
        return {
            "status": "error",
            "code": "OPERATION_NOT_FOUND",
            "message": (
                f"Method '{operation_method}' not found for '{path}'. "
                f"Available methods: {available}"
            ),
        }

    op = model.operation_at(path, operation_method)
    if op is None:
        return {
            "status": "error",
            "code": "SCHEMA_PARSE_ERROR",
            "message": f"Unexpected operation format for {operation_method} {path}",
        }

    schema_truncated = False

    # Resolve $ref in parameters
    parameters: list[dict] = []
    for param in op.parameters:
        resolved, truncated = model.resolve_refs(param.raw)
        schema_truncated = schema_truncated or truncated
        parameters.append(resolved)

    # Resolve $ref in requestBody → flatten to field list
    request_body_fields: list[dict] = []
    if op.request_body is not None:
        _, truncated = model.resolve_refs(op.request_body.raw)
        schema_truncated = schema_truncated or truncated
        request_body_fields = op.request_body.fields()

    # Resolve $ref in responses
    responses: dict = {}
    for status_code, response in op.responses.items():
        resolved_resp, truncated = model.resolve_refs(response.raw)
        schema_truncated = schema_truncated or truncated
        responses[status_code] = resolved_resp

    # Confirmation annotation
    conf = check_confirmation(operation_method.upper(), path)

    result = {
        "path": path,
        "method": operation_method.upper(),
        "operationId": op.operation_id,
        "summary": op.summary,
        "description": op.description,
        "parameters": parameters,
        "request_body_fields": request_body_fields,
        "responses": responses,
        "requires_confirmation": conf["requires_confirmation"],
        "confirmation_level": conf["confirmation_level"],
    }
    if schema_truncated:
        result["schema_truncated"] = True

    return result


# =========================================================================== #
# Execute helper functions
# =========================================================================== #


def _substitute_path_params(
    path: str, path_params: dict[str, Any]
) -> tuple[str, list[str]]:
    """
    Replace {paramName} placeholders in path with values from path_params.

    Returns:
        (resolved_path, missing_params)
        missing_params is an empty list when all placeholders were satisfied.
    """
    placeholders = re.findall(r"\{([^}]+)\}", path)
    missing: list[str] = []
    resolved = path
    for ph in placeholders:
        if ph in path_params:
            resolved = resolved.replace(f"{{{ph}}}", str(path_params[ph]))
        else:
            missing.append(ph)
    return resolved, missing


def _validate_required_params(
    operation: dict[str, Any],
    path_params: dict[str, Any],
    query_params: dict[str, Any],
    body: dict[str, Any] | None,
    resolved_path: str = "",
    model: OpenAPISpec | None = None,
) -> dict[str, Any] | None:
    """
    Check that all required parameters are present.

    A required path parameter counts as satisfied when it was supplied via
    path_params *or* already substituted inline into the path (i.e. its
    ``{name}`` placeholder no longer appears in resolved_path). This avoids a
    false VALIDATION_ERROR when the caller passes a fully-resolved path such as
    "/vdbs/vdb-123" without a path_params dict.

    Returns an error dict if any required param is missing, else None.
    """
    missing: list[str] = []

    # Check parameter-level required fields (path, query)
    for param in operation.get("parameters", []) or []:
        if not isinstance(param, dict):
            continue
        if not param.get("required", False):
            continue
        name = param.get("name", "")
        location = param.get("in", "")
        if location == "path":
            unresolved = f"{{{name}}}" in resolved_path
            if unresolved and name not in path_params:
                missing.append(f"path:{name}")
        elif location == "query" and name not in query_params:
            missing.append(f"query:{name}")

    # Check required body fields
    request_body = operation.get("requestBody", {}) or {}
    if request_body.get("required", False) and body is None:
        missing.append("requestBody")
    elif body is not None and request_body and model is not None:
        # Real DCT requestBody schemas are $ref pointers carrying no inline
        # required key, so RequestBody resolves the pointer (via the shared
        # OpenAPISpec model) before reading required field names.
        for field in RequestBody(model, request_body).required_field_names():
            if field not in body:
                missing.append(f"body:{field}")

    if missing:
        return {
            "status": "error",
            "code": "VALIDATION_ERROR",
            "missing_fields": missing,
            "message": f"Required fields missing: {missing}",
        }
    return None


def _secret_for_identity(identity_name: str) -> str | None:
    """Paired secret field name for an identity field, or None.

    A secret rarely stands alone: it accompanies a non-secret identity.
    ``username`` -> ``password`` (and ``masking_username`` ->
    ``masking_password``, ``source_username`` -> ``source_password``);
    ``access_key`` -> ``secret_key`` for S3-style cloud storage, where the
    access key id is an identifier and only the secret key is sensitive.
    Matches only the identity suffixes below, so unrelated fields
    (``user_count``, ``hostname``, ``ssh_key`` — itself a UUID reference, not
    a secret) never pair.
    """
    low = identity_name.lower()
    if low.endswith("username"):
        return identity_name[: -len("username")] + "password"
    if low.endswith("user"):
        return identity_name[: -len("user")] + "password"
    if low.endswith("access_key"):
        return identity_name[: -len("access_key")] + "secret_key"
    return None


# Credential references that stand in for a password (mutually exclusive with
# it per the connector schema): when one is already supplied in a container,
# no password is needed there (e.g. SFTP key auth uses ssh_key instead). These
# are identifiers/references, not raw secrets, so they are never captured as
# masked input even if a spec happened to annotate them.
_PASSWORD_ALTERNATIVES = ("ssh_key", "credential_path_id")

# DCT annotates every secret-bearing request field in the OpenAPI spec with
# this extension. It is the authoritative list of credential field names;
# identity pairing (above) only reaches secrets that accompany an identity, so
# standalone annotated secrets (e.g. encryption_key, data_key) are caught by
# name here instead of by a brittle substring heuristic.
_CREDENTIAL_FIELD_ANNOTATION = "x-dct-toolkit-credential-field"

# Per-spec cache keyed by id(spec); the spec is loaded once at startup.
_credential_field_cache: dict[int, frozenset[str]] = {}


def _collect_annotated_credential_fields(node: Any, out: set[str]) -> None:
    """Recursively collect property names annotated as credential fields."""
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            for prop_name, prop_schema in props.items():
                if (
                    isinstance(prop_schema, dict)
                    and prop_schema.get(_CREDENTIAL_FIELD_ANNOTATION) is True
                ):
                    out.add(prop_name)
        for value in node.values():
            _collect_annotated_credential_fields(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect_annotated_credential_fields(item, out)


def _annotated_credential_fields(spec: dict[str, Any] | None) -> frozenset[str]:
    """Names of every field the DCT spec annotates as a credential (cached)."""
    if not spec:
        return frozenset()
    key = id(spec)
    cached = _credential_field_cache.get(key)
    if cached is None:
        found: set[str] = set()
        _collect_annotated_credential_fields(spec, found)
        cached = frozenset(found) - frozenset(_PASSWORD_ALTERNATIVES)
        _credential_field_cache[key] = cached
    return cached


def _collect_missing_secrets(
    obj: Any, out: list[str], credential_fields: frozenset[str]
) -> None:
    """Recursively gather secret field names that must be captured out-of-band.

    Walks the actual request body (not the schema): DCT create bodies are often
    discriminated unions the spec flattener cannot enumerate (e.g.
    POST /environments), yet the nested ``host_parameters`` carries
    username/password. Two sources feed the list:

    1. Any field the spec annotates as a credential (``credential_fields``) that
       appears in the body — the model must never supply it inline, so we flag
       it whether present (strip + recapture) or paired-and-absent.
    2. Identity pairing — an identity field (``username``) whose paired secret
       (``password``) is absent from the same container, unless a
       mutually-exclusive credential alternative (``ssh_key``) is supplied.
    """
    if isinstance(obj, dict):
        for value in obj.values():
            _collect_missing_secrets(value, out, credential_fields)
        for key in obj:
            if key in credential_fields and key not in out:
                out.append(key)
        for key in obj:
            secret = _secret_for_identity(key)
            if not secret or secret in obj or secret in out:
                continue
            if secret.endswith("password") and any(
                obj.get(alt) for alt in _PASSWORD_ALTERNATIVES
            ):
                continue
            out.append(secret)
    elif isinstance(obj, list):
        for item in obj:
            _collect_missing_secrets(item, out, credential_fields)


def _missing_sensitive_fields(
    body: dict[str, Any] | None, credential_fields: frozenset[str] = frozenset()
) -> list[str]:
    """Secret-bearing fields the body must not carry inline, in first-seen order.

    Value-based (not schema-based) so nested and discriminated-union bodies are
    handled uniformly. Combines spec-annotated credential fields with identity
    pairing; the host captures each out-of-band and re-calls with it applied.
    """
    missing: list[str] = []
    _collect_missing_secrets(body or {}, missing, credential_fields)
    return missing


def _classify_operation_type(method: str) -> str:
    """Map HTTP method to a human-readable operation type."""
    if method == "GET":
        return "read"
    if method == "DELETE":
        return "destructive"
    return "mutating"


def _extract_http_status(error_message: str) -> int | None:
    """Try to extract an integer HTTP status code from a DCTClientError message."""
    match = re.search(r"HTTP (\d{3})", error_message)
    if match:
        return int(match.group(1))
    return None


# $ref resolution, path-template matching, and request-body flattening now live
# in the shared OpenAPISpec model (tools/core/spec_model.py).
