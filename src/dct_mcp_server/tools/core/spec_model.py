"""
Standardized object model over the DCT OpenAPI spec.

Historically every consumer of the spec (discovery/execute in ``dynamic.py``,
the fuzzy ranker in ``endpoint_discovery.py``, and the two code generators in
``toolsgenerator/driver.py`` and ``tools/core/tool_factory.py``) walked the raw
nested ``dict`` by hand and re-implemented ``$ref`` resolution, ``allOf`` merging,
request-body flattening, and path-template matching.  Those re-implementations
drifted: cycle detection, depth limits, and truncation handling all differed.

This module is the single source of truth for that structure.  It wraps the raw
spec ``dict`` in lightweight, lazily-evaluated objects so consumers can ask for
*operations*, *request bodies*, *responses*, and *domain objects* directly:

    spec = OpenAPISpec.wrap(get_cached_spec())
    op = spec.operation_at("/vdbs/{vdbId}", "GET")
    for field in op.request_body.fields():
        ...
    dsource = spec.domain_object("DSource")   # -> DSource(SchemaObject)

Design constraints (see DLPXECO-14248):

* **Spec/metadata model, not data models.**  These classes describe the *shape*
  of requests/responses/objects; they are never instantiated with live payloads.
* **Generic wrapper + curated key objects.**  One generic :class:`SchemaObject`
  covers all ~691 ``components/schemas``; :class:`DSource` and :class:`VDB` are
  named subclasses for the two highest-value domain objects.
* **Runtime wrappers over the cached spec.**  No build step; instances wrap the
  already-cached dict and are memoized by object identity, so they stay in sync
  with the live-downloaded spec.
"""

from __future__ import annotations

import re
from typing import Any, Iterator

from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

# HTTP methods that denote an operation on a path item (everything else in a
# path item — "parameters", "summary", vendor extensions — is metadata).
HTTP_METHODS: frozenset[str] = frozenset({"get", "post", "put", "patch", "delete"})

# Default maximum $ref resolution depth, guarding against circular schemas.
# Matches the historical _MAX_REF_DEPTH used by dynamic.py.
DEFAULT_MAX_REF_DEPTH = 10


# =========================================================================== #
# Spec root
# =========================================================================== #


class OpenAPISpec:
    """Wrapper around a parsed OpenAPI spec dict.

    Owns the raw document and is the single home for ``$ref`` resolution.  Two
    resolution styles are offered because consumers need different things:

    * :meth:`resolve_pointer` — resolve one ``$ref`` string to its target node
      (the single-level lookup the code generators use).
    * :meth:`resolve_refs` — recursively inline every ``$ref`` in a subtree,
      with cycle detection and a depth limit (what discovery's
      ``get_operation_schema`` needs before handing a schema to the LLM).
    """

    __slots__ = ("raw", "_schema_object_cache")

    # Identity-keyed cache of wrappers, so repeatedly wrapping the same cached
    # spec dict (e.g. on every discovery/execute call) is free and downstream
    # caches (schema objects, the discovery index) stay warm across calls.
    _WRAPPER_CACHE: dict[int, "OpenAPISpec"] = {}

    def __init__(self, raw: dict[str, Any]):
        if not isinstance(raw, dict):
            raise TypeError(f"OpenAPISpec expects a dict, got {type(raw).__name__}")
        self.raw = raw
        self._schema_object_cache: dict[str, SchemaObject] = {}

    @classmethod
    def wrap(cls, raw: dict[str, Any] | None) -> "OpenAPISpec | None":
        """Return an ``OpenAPISpec`` for *raw*, memoized by object identity.

        Returns ``None`` when *raw* is falsy so callers can treat "spec not
        loaded yet" uniformly.  The cached spec dict is replaced (not mutated)
        on reload, so keying by ``id(raw)`` is a safe invalidation signal.
        """
        if not raw:
            return None
        key = id(raw)
        cached = cls._WRAPPER_CACHE.get(key)
        if cached is not None and cached.raw is raw:
            return cached
        wrapper = cls(raw)
        cls._WRAPPER_CACHE = {key: wrapper}  # only the current spec is useful
        return wrapper

    # ------------------------------------------------------------------ #
    # Top-level accessors
    # ------------------------------------------------------------------ #

    @property
    def paths(self) -> dict[str, Any]:
        return self.raw.get("paths", {}) or {}

    @property
    def components(self) -> dict[str, Any]:
        return self.raw.get("components", {}) or {}

    @property
    def schemas(self) -> dict[str, Any]:
        return self.components.get("schemas", {}) or {}

    # ------------------------------------------------------------------ #
    # $ref resolution
    # ------------------------------------------------------------------ #

    def resolve_pointer(self, ref: str) -> Any:
        """Resolve a single JSON ``$ref`` pointer like ``#/components/schemas/DSource``.

        This is the single-level lookup historically duplicated as
        ``resolve_ref`` (driver.py) and ``_resolve_ref`` (tool_factory.py).
        Raises ``ValueError`` for unsupported (non-fragment) refs and
        ``KeyError`` when the target is absent.
        """
        if not ref.startswith("#/"):
            raise ValueError(f"Unsupported ref format: {ref}")
        node: Any = self.raw
        for part in ref.lstrip("#/").split("/"):
            node = node[part]
        return node

    def resolve_refs(
        self,
        obj: Any,
        *,
        max_depth: int = DEFAULT_MAX_REF_DEPTH,
        depth: int = 0,
        visited: frozenset[str] = frozenset(),
    ) -> tuple[Any, bool]:
        """Recursively inline every ``$ref`` in *obj*.

        Returns ``(resolved_obj, truncated)`` where *truncated* is ``True`` if a
        cycle or the depth limit was hit.  Behaviour matches the former
        ``dynamic.py._resolve_refs`` exactly, including the marker dicts emitted
        for truncation / missing refs, so it is a drop-in replacement.
        """
        if depth > max_depth:
            return {"$ref_truncated": True, "reason": "max_depth_exceeded"}, True

        if not isinstance(obj, dict):
            return obj, False

        if "$ref" in obj:
            ref = obj["$ref"]
            if ref in visited:
                return {
                    "$ref_truncated": True,
                    "reason": "cycle_detected",
                    "ref": ref,
                }, True
            try:
                target = self.resolve_pointer(ref)
            except (KeyError, TypeError, ValueError) as exc:
                return {
                    "status": "error",
                    "code": "SCHEMA_REF_NOT_FOUND",
                    "ref": ref,
                    "message": str(exc),
                }, False
            return self.resolve_refs(
                target, max_depth=max_depth, depth=depth + 1, visited=visited | {ref}
            )

        truncated = False
        result: dict[str, Any] = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                resolved_v, child_truncated = self.resolve_refs(
                    value, max_depth=max_depth, depth=depth + 1, visited=visited
                )
                truncated = truncated or child_truncated
                result[key] = resolved_v
            elif isinstance(value, list):
                resolved_list: list[Any] = []
                for item in value:
                    resolved_item, child_truncated = self.resolve_refs(
                        item, max_depth=max_depth, depth=depth + 1, visited=visited
                    )
                    truncated = truncated or child_truncated
                    resolved_list.append(resolved_item)
                result[key] = resolved_list
            else:
                result[key] = value
        return result, truncated

    # ------------------------------------------------------------------ #
    # Operations
    # ------------------------------------------------------------------ #

    def operations(self) -> Iterator["Operation"]:
        """Yield an :class:`Operation` for every (path, HTTP method) in the spec."""
        for path, item in self.paths.items():
            if not isinstance(item, dict):
                continue
            for method, op in item.items():
                if method.lower() not in HTTP_METHODS or not isinstance(op, dict):
                    continue
                yield Operation(self, path, method.upper(), op)

    def find_path_item(self, path: str) -> dict[str, Any] | None:
        """Return the path-item dict for *path*.

        Tries an exact match first, then treats ``{paramName}`` segments in spec
        paths as wildcards so a fully-resolved path (``/vdbs/vdb-123``) matches
        its template (``/vdbs/{vdbId}``).  Centralizes the former
        ``dynamic.py._find_path_item``.
        """
        paths = self.paths
        if path in paths:
            return paths[path]

        target_segments = path.split("/")
        for spec_path, item in paths.items():
            spec_segments = spec_path.split("/")
            if len(spec_segments) != len(target_segments):
                continue
            if all(
                sp == tp or (sp.startswith("{") and sp.endswith("}"))
                for sp, tp in zip(spec_segments, target_segments)
            ):
                return item
        return None

    def operation_at(self, path: str, method: str) -> "Operation | None":
        """Return the :class:`Operation` for *path* + *method*, or ``None``."""
        item = self.find_path_item(path)
        if item is None:
            return None
        op = item.get(method.lower())
        if not isinstance(op, dict):
            return None
        return Operation(self, path, method.upper(), op)

    # ------------------------------------------------------------------ #
    # Domain objects (components/schemas)
    # ------------------------------------------------------------------ #

    def schema_object(self, schema: dict[str, Any]) -> "SchemaObject":
        """Wrap an inline schema dict in a :class:`SchemaObject`."""
        return SchemaObject(self, schema)

    def domain_object(self, name: str) -> "SchemaObject | None":
        """Return the named ``components/schemas`` entry as a :class:`SchemaObject`.

        Returns a curated subclass (:class:`DSource`, :class:`VDB`) when one is
        registered for *name*, otherwise the generic :class:`SchemaObject`.
        Returns ``None`` if the schema is absent.  Results are cached per spec.
        """
        if name in self._schema_object_cache:
            return self._schema_object_cache[name]
        raw_schema = self.schemas.get(name)
        if raw_schema is None:
            return None
        cls = _CURATED_DOMAIN_OBJECTS.get(name, SchemaObject)
        obj = cls(self, raw_schema, name=name)
        self._schema_object_cache[name] = obj
        return obj


# =========================================================================== #
# Operation
# =========================================================================== #


class Operation:
    """A single API operation — one (path, HTTP method) pair."""

    __slots__ = ("spec", "path", "method", "raw")

    def __init__(self, spec: OpenAPISpec, path: str, method: str, raw: dict[str, Any]):
        self.spec = spec
        self.path = path
        self.method = method.upper()
        self.raw = raw

    @property
    def operation_id(self) -> str:
        return self.raw.get("operationId", "") or ""

    @property
    def summary(self) -> str:
        return self.raw.get("summary", "") or ""

    @property
    def description(self) -> str:
        return self.raw.get("description", "") or ""

    @property
    def tags(self) -> list[str]:
        return self.raw.get("tags", []) or []

    @property
    def parameters(self) -> list["Parameter"]:
        return [
            Parameter(self.spec, p)
            for p in self.raw.get("parameters", []) or []
            if isinstance(p, dict)
        ]

    @property
    def request_body(self) -> "RequestBody | None":
        rb = self.raw.get("requestBody")
        if not rb:
            return None
        return RequestBody(self.spec, rb)

    @property
    def responses(self) -> dict[str, "Response"]:
        return {
            str(status): Response(self.spec, str(status), resp)
            for status, resp in (self.raw.get("responses", {}) or {}).items()
        }

    @property
    def path_param_names(self) -> list[str]:
        """Names of ``{placeholder}`` path parameters declared in the path."""
        return re.findall(r"\{([^}]+)\}", self.path)


# =========================================================================== #
# Parameter
# =========================================================================== #


class Parameter:
    """A path/query/header parameter on an operation."""

    __slots__ = ("spec", "raw")

    def __init__(self, spec: OpenAPISpec, raw: dict[str, Any]):
        self.spec = spec
        self.raw = raw

    @property
    def name(self) -> str:
        return self.raw.get("name", "") or ""

    @property
    def location(self) -> str:
        """Where the parameter lives — the OpenAPI ``in`` value (path/query/...)."""
        return self.raw.get("in", "") or ""

    @property
    def required(self) -> bool:
        return bool(self.raw.get("required", False))

    @property
    def description(self) -> str:
        return self.raw.get("description", "") or ""

    @property
    def schema(self) -> dict[str, Any]:
        return self.raw.get("schema", {}) or {}


# =========================================================================== #
# RequestBody
# =========================================================================== #


class RequestBody:
    """An operation's ``requestBody``.

    Real DCT request bodies are ``$ref`` pointers to ``components/schemas``
    carrying no inline ``required`` key, so :meth:`schema_object` resolves the
    pointer before exposing properties — without it, required-field checks were
    silent no-ops for every mutating endpoint.
    """

    __slots__ = ("spec", "raw")

    def __init__(self, spec: OpenAPISpec, raw: dict[str, Any]):
        self.spec = spec
        self.raw = raw

    @property
    def required(self) -> bool:
        return bool(self.raw.get("required", False))

    @property
    def content(self) -> dict[str, Any]:
        return self.raw.get("content", {}) or {}

    def _primary_schema_dict(self) -> dict[str, Any]:
        """Raw schema of the first media type (DCT bodies are application/json)."""
        for media_obj in self.content.values():
            if isinstance(media_obj, dict):
                return media_obj.get("schema", {}) or {}
        return {}

    def schema_object(self) -> "SchemaObject | None":
        """The request body schema as a :class:`SchemaObject` (``$ref`` resolved)."""
        schema = self._primary_schema_dict()
        if not schema:
            return None
        return SchemaObject(self.spec, schema)

    def required_field_names(self) -> list[str]:
        """Top-level required field names of the (ref-resolved) body schema.

        Used by execute's best-effort body validation.  Deliberately reads only
        the resolved schema's top-level ``required`` list (not ``allOf``-merged
        requireds) to preserve the historically lenient validation behaviour.
        """
        schema = self._primary_schema_dict()
        if not schema:
            return []
        resolved, _ = self.spec.resolve_refs(schema)
        if not isinstance(resolved, dict):
            return []
        return list(resolved.get("required", []) or [])

    def fields(self) -> list[dict[str, Any]]:
        """Flatten the body schema into ``{name, required, type, description}`` rows.

        Replaces the former ``dynamic.py._flatten_request_body``.
        """
        obj = self.schema_object()
        if obj is None:
            return []
        required = obj.required
        out: list[dict[str, Any]] = []
        for name, prop in obj.properties.items():
            if not isinstance(prop, dict):
                continue
            out.append(
                {
                    "name": name,
                    "required": name in required,
                    "type": prop.get("type", "object"),
                    "description": prop.get("description", "") or "",
                }
            )
        return out


# =========================================================================== #
# Response
# =========================================================================== #


class Response:
    """A single response entry keyed by status code."""

    __slots__ = ("spec", "status_code", "raw")

    def __init__(self, spec: OpenAPISpec, status_code: str, raw: dict[str, Any]):
        self.spec = spec
        self.status_code = status_code
        self.raw = raw

    @property
    def description(self) -> str:
        return self.raw.get("description", "") or ""

    @property
    def content(self) -> dict[str, Any]:
        return self.raw.get("content", {}) or {}

    def schema_object(self) -> "SchemaObject | None":
        """The response payload schema as a :class:`SchemaObject` (``$ref`` resolved)."""
        for media_obj in self.content.values():
            if isinstance(media_obj, dict):
                schema = media_obj.get("schema", {}) or {}
                if schema:
                    return SchemaObject(self.spec, schema)
        return None


# =========================================================================== #
# SchemaObject (domain objects: dSource, VDB, request/response bodies, …)
# =========================================================================== #


class SchemaObject:
    """A ``components/schemas`` entry or any inline schema.

    Resolves a top-level ``$ref``, merges ``allOf`` composition, and distinguishes
    *key properties* (action-specific) from large inherited base schemas — the
    logic formerly living only in ``driver.py.resolve_schema_properties``.
    """

    __slots__ = ("spec", "raw", "name", "_resolved")

    def __init__(self, spec: OpenAPISpec, raw: dict[str, Any], name: str | None = None):
        self.spec = spec
        self.raw = raw
        self.name = name
        self._resolved: tuple[dict[str, Any], list[str], set[str]] | None = None

    def _resolve(self) -> tuple[dict[str, Any], list[str], set[str]]:
        """Compute ``(properties, required, key_properties)`` once, then cache."""
        if self._resolved is not None:
            return self._resolved

        schema = self.raw
        if "$ref" in schema:
            schema = self.spec.resolve_pointer(schema["$ref"])

        if "allOf" in schema:
            properties: dict[str, Any] = {}
            required: list[str] = []
            key_properties: set[str] = set()

            for sub in schema["allOf"]:
                is_ref = isinstance(sub, dict) and "$ref" in sub
                if is_ref:
                    sub = self.spec.resolve_pointer(sub["$ref"])
                if not isinstance(sub, dict):
                    continue

                if "allOf" in sub:
                    nested = SchemaObject(self.spec, sub)
                    properties.update(nested.properties)
                    required.extend(nested.required)
                    # Base-schema key properties are intentionally not propagated.
                else:
                    props = sub.get("properties", {}) or {}
                    properties.update(props)
                    required.extend(sub.get("required", []) or [])
                    # Inline objects and small $ref'd schemas (<=5 props) are
                    # action-specific; large $ref'd schemas are inherited bases.
                    if not is_ref or len(props) <= 5:
                        key_properties.update(props.keys())

            self._resolved = (properties, required, key_properties)
        else:
            props = schema.get("properties", {}) or {}
            self._resolved = (
                props,
                schema.get("required", []) or [],
                set(props.keys()),
            )

        return self._resolved

    @property
    def properties(self) -> dict[str, Any]:
        return self._resolve()[0]

    @property
    def required(self) -> list[str]:
        return self._resolve()[1]

    @property
    def key_properties(self) -> set[str]:
        """Property names from action-specific sub-schemas (not inherited bases)."""
        return self._resolve()[2]


# --------------------------------------------------------------------------- #
# Curated domain objects
# --------------------------------------------------------------------------- #


class DSource(SchemaObject):
    """The DCT ``DSource`` domain object (a linked/ingested source dataset)."""

    SCHEMA_NAME = "DSource"


class VDB(SchemaObject):
    """The DCT ``VDB`` domain object (a provisioned virtual database)."""

    SCHEMA_NAME = "VDB"


# Registry consulted by OpenAPISpec.domain_object() to upgrade a generic
# SchemaObject to a curated subclass.  Add high-value objects here only.
_CURATED_DOMAIN_OBJECTS: dict[str, type[SchemaObject]] = {
    DSource.SCHEMA_NAME: DSource,
    VDB.SCHEMA_NAME: VDB,
}
