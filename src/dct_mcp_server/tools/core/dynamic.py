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
from typing import Any

from mcp.server.fastmcp import FastMCP

from dct_mcp_server.core.auth import resolve_auth
from dct_mcp_server.core.client_registry import ClientRegistry
from dct_mcp_server.core.decorators import log_tool_execution
from dct_mcp_server.core.exceptions import DCTClientError
from dct_mcp_server.core.logging import get_logger
from dct_mcp_server.tools.core.confirmation_resolver import check_confirmation
from dct_mcp_server.tools.core.confirmation_token import (
    make_confirmation_token,
    verify_confirmation_token,
)
from dct_mcp_server.tools.core.spec_cache import get_cached_spec
from dct_mcp_server.tools.core.spec_model import OpenAPISpec, RequestBody

logger = get_logger(__name__)

# Pagination hard cap
_MAX_PAGE_SIZE = 50


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

    app.add_tool(_discovery_fn, name="discovery")
    logger.info("  Registered: discovery")

    app.add_tool(_execute_fn, name="execute")
    logger.info("  Registered: execute")

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
    ) -> dict[str, Any]:
        """
        Validate, confirm, and dispatch a DCT API call.

        The execute tool acts as a universal DCT API dispatcher.  It:
          1. Substitutes {paramName} placeholders in path using path_params
          2. Looks up the operation in the cached spec (OPERATION_NOT_FOUND if absent)
          3. Validates required parameters against the spec (VALIDATION_ERROR if missing)
          4. Checks confirmation gates for destructive operations. A destructive
             op returns confirmation_required (with a confirmation_token) until the
             caller re-calls with that exact token — a bare confirmed=true cannot
             bypass it.
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

        Returns:
            On confirmation required: {"status": "confirmation_required", "confirmation_level": str, ...}
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
            missing_secrets = _missing_sensitive_fields(body)
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
        # Step 4 — Confirmation gate
        # ---------------------------------------------------------------- #
        if method_upper in ("DELETE", "POST", "PUT", "PATCH"):
            conf = check_confirmation(method_upper, resolved_path)
            # A bare confirmed=true does NOT bypass the gate: the caller must echo
            # the server-issued confirmation_token from the prior
            # confirmation_required response, proving it saw the STOP instructions.
            if conf["requires_confirmation"] and not verify_confirmation_token(
                confirmation_token, method_upper, resolved_path
            ):
                return {
                    "status": "confirmation_required",
                    "confirmation_level": conf["confirmation_level"],
                    "message": (
                        conf["message_template"]
                        or f"This operation ({method_upper} {resolved_path}) requires confirmation."
                    ),
                    "confirmation_token": make_confirmation_token(
                        method_upper, resolved_path
                    ),
                    "operation": {"path": resolved_path, "method": method_upper},
                    "instructions": (
                        "STOP. Display the message to the user and obtain their EXPLICIT "
                        "approval before proceeding — do NOT approve on their behalf. Once "
                        "the user approves, re-call execute with the IDENTICAL arguments "
                        "plus confirmation_token set to the value above. A bare "
                        "confirmed=true is ignored; the token is required."
                    ),
                }

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
            return {
                "status": "success",
                "operation_type": operation_type,
                "response": response,
            }
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

    A password rarely stands alone: it accompanies an identity. ``username`` ->
    ``password``, ``masking_username`` -> ``masking_password``, ``db_user`` ->
    ``db_password``. Matches only names ending in ``username``/``user`` so
    unrelated fields (``user_count``, ``hostname``) never pair.
    """
    low = identity_name.lower()
    if low.endswith("username"):
        return identity_name[: -len("username")] + "password"
    if low.endswith("user"):
        return identity_name[: -len("user")] + "password"
    return None


def _collect_missing_secrets(obj: Any, out: list[str]) -> None:
    """Recursively gather paired secret names absent from the body value.

    Walks the actual request body (not the schema): DCT create bodies are often
    discriminated unions the spec flattener cannot enumerate (e.g.
    POST /environments), yet the nested ``host_parameters`` carries
    username/password. In every object container, an identity field whose paired
    secret is absent from that same container marks the secret as needed.
    """
    if isinstance(obj, dict):
        for value in obj.values():
            _collect_missing_secrets(value, out)
        for key in obj:
            secret = _secret_for_identity(key)
            if secret and secret not in obj and secret not in out:
                out.append(secret)
    elif isinstance(obj, list):
        for item in obj:
            _collect_missing_secrets(item, out)


def _missing_sensitive_fields(body: dict[str, Any] | None) -> list[str]:
    """Secret-shaped fields the body needs but omits, found by identity pairing.

    Value-based (not schema-based) so nested and discriminated-union bodies are
    handled uniformly. Returns the distinct leaf secret names in first-seen
    order; the host captures them out-of-band and re-calls with them applied.
    """
    missing: list[str] = []
    _collect_missing_secrets(body or {}, missing)
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
