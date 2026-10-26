"""
connector_secrets.py — AppData connector-secret detection (DLPXECO-14781).

Detects connector parameters declared ``"format": "password"`` in a toolkit's
schema.json and routes them through the sensitive-input gate.

Public API:
    SecretPath, FlaggedLocation, ConnectorResult
    walk_secret_paths(schema, root, *, context) -> frozenset[SecretPath]
    expand_and_flag(sub_object, value, records) -> list[FlaggedLocation]
    parse_applied(sensitive_applied) -> tuple[frozenset[str], frozenset[str]]
    drop_applied(flagged, names, locations) -> list[FlaggedLocation]
    find_flagged_connector_secrets(...) -> ConnectorResult  (async, never raises)
    clear_caches() -> None
"""
from __future__ import annotations

import asyncio
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable

from dct_mcp_server.config.loader import load_appdata_operations, match_appdata_operation
from dct_mcp_server.core.exceptions import DCTClientError
from dct_mcp_server.core.logging import get_logger
from dct_mcp_server.tools.core.host_trust import _SENSITIVE_NONCE_ENV, host_nonce_ok

logger = get_logger(__name__)

# Walker limits
_MAX_DEPTH = 32
_MAX_NODES = 10_000

# Cache limits and TTLs (seconds)
_MAX_CACHE_ENTRIES = 256
_VERSION_BINDING_TTL_S = 900   # 15 min — id→version binding
_OBJECT_TTL_S = 900            # 15 min — referenced object id→next_id
_NEGATIVE_TTL_S = 60           # 60 s  — failures
_OBJECT_NEGATIVE_TTL_S = 60


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SecretPath:
    """A password-format field path within a toolkit schema."""
    path: str           # dotted path with [*] for arrays, e.g. "nodes[*].password"
    required: bool      # field is in parent "required" list
    conditional: bool   # inside oneOf/anyOf/if/then/else/dependencies


@dataclass(frozen=True)
class FlaggedLocation:
    """A concrete secret location within the request body."""
    name: str           # leaf property name
    location: str       # full dotted path from body root, e.g. "parameters.nodes[0].password"


@dataclass
class ConnectorResult:
    """Result of AppData connector-secret detection for one execute call."""
    flagged: list[FlaggedLocation] = field(default_factory=list)
    covered_sub_objects: frozenset[str] = field(default_factory=frozenset)


# ─────────────────────────────────────────────────────────────────────────────
# Schema walker
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_ref(ref: str, root: dict) -> dict | None:
    """Resolve a JSON pointer $ref against *root*. Returns None on failure."""
    if not ref.startswith("#"):
        return None
    parts = ref[1:].lstrip("/").split("/") if ref != "#" else []
    node = root
    try:
        for part in parts:
            part = part.replace("~1", "/").replace("~0", "~")
            node = node[part]
        return node if isinstance(node, dict) else None
    except (KeyError, TypeError):
        return None


def walk_secret_paths(
    schema: Any,
    root: dict | None = None,
    *,
    context: str = "",
) -> frozenset[SecretPath]:
    """Recursively walk *schema* and return all password-format field paths.

    Args:
        schema: The JSON-schema object to walk (the definition body).
        root: The $ref resolution root. Defaults to *schema* if None.
        context: Caller label for warning messages (e.g. toolkit id).

    Returns:
        frozenset of SecretPath. Empty on a non-dict root (with a warning).
    """
    if not isinstance(schema, dict):
        if schema is not None:
            logger.warning(
                "AppData secret detection: non-dict schema root; context=%s", context
            )
        return frozenset()

    if root is None:
        root = schema

    results: set[SecretPath] = set()
    visited_refs: set[str] = set()
    node_count = [0]

    def _walk(node: Any, path: str, required: bool, conditional: bool, depth: int) -> None:
        if depth > _MAX_DEPTH:
            logger.warning(
                "AppData secret detection: max depth %d reached; context=%s path=%s",
                _MAX_DEPTH, context, path,
            )
            return
        if node_count[0] >= _MAX_NODES:
            return
        node_count[0] += 1

        if not isinstance(node, dict):
            return

        # $ref resolution
        if "$ref" in node:
            ref = node["$ref"]
            if ref in visited_refs:
                return  # cycle guard
            visited_refs.add(ref)
            resolved = _resolve_ref(ref, root)
            if resolved is None:
                logger.warning(
                    "AppData secret detection: unresolvable $ref %r; context=%s", ref, context
                )
                visited_refs.discard(ref)
                return
            _walk(resolved, path, required, conditional, depth + 1)
            visited_refs.discard(ref)
            return

        # password-format leaf — record and do NOT descend (EC-16)
        if node.get("format") == "password":
            leaf = path.rsplit(".", 1)[-1] if "." in path else path
            # strip array suffix for the name
            leaf = re.sub(r"\[\*\]$", "", leaf).split(".")[-1]
            results.add(SecretPath(path=path, required=required, conditional=conditional))
            return

        # properties
        req_set: set[str] = set(node.get("required", []) if isinstance(node.get("required"), list) else [])
        for prop_name, prop_schema in (node.get("properties") or {}).items():
            child_path = f"{path}.{prop_name}" if path else prop_name
            child_req = prop_name in req_set
            _walk(prop_schema, child_path, child_req, conditional, depth + 1)

        # array items
        items = node.get("items")
        if isinstance(items, dict):
            _walk(items, f"{path}[*]", False, conditional, depth + 1)
        elif isinstance(items, list):
            for i, item in enumerate(items):
                _walk(item, f"{path}[{i}]", False, conditional, depth + 1)

        # additionalProperties / patternProperties
        for kw in ("additionalProperties", "patternProperties"):
            val = node.get(kw)
            if isinstance(val, dict):
                if kw == "additionalProperties":
                    _walk(val, f"{path}.*", False, conditional, depth + 1)
                else:
                    for _pat, pschema in val.items():
                        _walk(pschema, f"{path}.*", False, conditional, depth + 1)

        # allOf — same path, conditional unchanged
        for sub in (node.get("allOf") or []):
            _walk(sub, path, False, conditional, depth + 1)

        # oneOf, anyOf, if/then/else, dependencies, dependentSchemas → conditional=True
        for kw in ("oneOf", "anyOf"):
            for sub in (node.get(kw) or []):
                _walk(sub, path, False, True, depth + 1)
        for kw in ("if", "then", "else"):
            sub = node.get(kw)
            if isinstance(sub, dict):
                _walk(sub, path, False, True, depth + 1)
        for kw in ("dependencies", "dependentSchemas"):
            val = node.get(kw)
            if isinstance(val, dict):
                for _dep_name, dep_schema in val.items():
                    if isinstance(dep_schema, dict):
                        _walk(dep_schema, path, False, True, depth + 1)

    _walk(schema, "", False, False, 0)
    # Remove the empty-string root entry if any
    return frozenset(p for p in results if p.path)


# ─────────────────────────────────────────────────────────────────────────────
# Definition-key lookup helpers
# ─────────────────────────────────────────────────────────────────────────────

# Maps logical definition name → (toolkit_response_keys_in_order, schema_extractor)
_DEFINITION_LOOKUP: dict[str, tuple[list[str], Callable[[dict], dict | None]]] = {
    "linked_source_definition": (
        ["linked_source_definition", "linkedSourceDefinition"],
        lambda d: d.get("parameters") if isinstance(d.get("parameters"), dict) else d,
    ),
    "virtual_source_definition": (
        ["virtual_source_definition", "virtualSourceDefinition"],
        lambda d: d.get("parameters") if isinstance(d.get("parameters"), dict) else d,
    ),
    "virtual_to_physical_definition": (
        ["virtual_to_physical_definition", "virtualToPhysicalDefinition"],
        lambda d: d.get("parameters") if isinstance(d.get("parameters"), dict) else d,
    ),
    "snapshot_parameters_definition": (
        ["snapshot_parameters_definition", "snapshotParametersDefinition", "snapshot_schema", "snapshotSchema"],
        lambda d: (
            d.get("schema") if isinstance(d.get("schema"), dict)
            else d.get("parameters") if isinstance(d.get("parameters"), dict)
            else d
        ),
    ),
    "source_config_definition": (
        ["discovery_definition.source_config_schema", "discoveryDefinition.sourceConfigSchema",
         "source_config_definition", "sourceConfigDefinition"],
        lambda d: d,
    ),
}


def _extract_definition_schema(toolkit_resp: dict, definition_name: str) -> dict | None:
    """Return the schema dict for *definition_name* from a toolkit API response."""
    keys_and_extractor = _DEFINITION_LOOKUP.get(definition_name)
    if not keys_and_extractor:
        return None
    keys, extractor = keys_and_extractor
    for key in keys:
        # Support dotted paths like "discovery_definition.source_config_schema"
        parts = key.split(".")
        node: Any = toolkit_resp
        for part in parts:
            if isinstance(node, dict):
                node = node.get(part)
            else:
                node = None
                break
        if isinstance(node, dict):
            return extractor(node)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Simple TTL LRU cache (pure stdlib, no third-party)
# ─────────────────────────────────────────────────────────────────────────────


class _TTLCache:
    """OrderedDict-based LRU cache with per-entry TTL."""

    def __init__(self, maxsize: int, ttl: float) -> None:
        self._cache: OrderedDict[Any, tuple[Any, float]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: Any) -> tuple[bool, Any]:
        """Return (found, value). Expired entries are evicted."""
        entry = self._cache.get(key)
        if entry is None:
            return False, None
        value, exp = entry
        if time.monotonic() > exp:
            del self._cache[key]
            return False, None
        self._cache.move_to_end(key)
        return True, value

    def set(self, key: Any, value: Any) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, time.monotonic() + self._ttl)
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# ToolkitSecretCache
# ─────────────────────────────────────────────────────────────────────────────


class _ToolkitSecretCache:
    """In-memory, single-event-loop cache for toolkit-derived SecretPath sets.

    Keying:
      version bindings: (base_url, toolkit_id) → version string, 15 min TTL
      derived records:  (base_url, toolkit_id, version) → dict[def_name, frozenset[SecretPath]], LRU 256
      global negative:  (base_url, toolkit_id) → True, 60 s TTL (5xx, timeout, parse errors)
      identity negative:(identity, base_url, toolkit_id) → True, 60 s TTL (401/403/404)
    """

    def __init__(self) -> None:
        self._version_bindings: _TTLCache = _TTLCache(512, _VERSION_BINDING_TTL_S)
        self._derived: _TTLCache = _TTLCache(_MAX_CACHE_ENTRIES, _VERSION_BINDING_TTL_S * 10)
        self._global_neg: _TTLCache = _TTLCache(512, _NEGATIVE_TTL_S)
        self._identity_neg: _TTLCache = _TTLCache(512, _NEGATIVE_TTL_S)
        # Single-flight: pending asyncio.Future per (base_url, toolkit_id)
        self._inflight: dict[tuple, asyncio.Future] = {}

    def clear(self) -> None:
        self._version_bindings.clear()
        self._derived.clear()
        self._global_neg.clear()
        self._identity_neg.clear()
        self._inflight.clear()

    async def get(
        self,
        client: Any,
        identity: str,
        toolkit_id: str,
        toolkit_path: str,
        context: str = "",
    ) -> dict[str, frozenset[SecretPath]] | None:
        """Return derived records or None on failure/fallback.

        Never raises.
        """
        from dct_mcp_server.config.config import get_dct_config
        try:
            cfg = get_dct_config(require_key=False)
            base_url = cfg.get("base_url", "")
        except Exception:
            base_url = ""

        g_key = (base_url, toolkit_id)
        i_key = (identity, base_url, toolkit_id)

        # Check negative caches
        found, _ = self._global_neg.get(g_key)
        if found:
            return None
        found, _ = self._identity_neg.get(i_key)
        if found:
            return None

        # Check version binding
        found_ver, version = self._version_bindings.get(g_key)
        if found_ver and version is not None:
            d_key = (base_url, toolkit_id, version)
            found_d, records = self._derived.get(d_key)
            if found_d:
                return records
            # version known but derived evicted — re-derive
            return await self._fetch_and_derive(
                client, identity, toolkit_id, toolkit_path, base_url,
                version, context,
            )

        # Cache miss — single-flight coalescing
        if g_key in self._inflight:
            try:
                return await asyncio.shield(self._inflight[g_key])
            except Exception:
                return None

        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._inflight[g_key] = fut
        try:
            result = await self._fetch_and_derive(
                client, identity, toolkit_id, toolkit_path, base_url,
                None, context,
            )
            fut.set_result(result)
            return result
        except Exception as exc:
            fut.set_exception(exc)
            return None
        finally:
            self._inflight.pop(g_key, None)

    async def _fetch_and_derive(
        self,
        client: Any,
        identity: str,
        toolkit_id: str,
        toolkit_path: str,
        base_url: str,
        known_version: str | None,
        context: str,
    ) -> dict[str, frozenset[SecretPath]] | None:
        """Fetch toolkit from DCT, derive records, update caches. None = fallback."""
        endpoint = toolkit_path.replace("{id}", toolkit_id)
        g_key = (base_url, toolkit_id)
        i_key = (identity, base_url, toolkit_id)

        try:
            resp = await client.make_request("GET", endpoint)
        except DCTClientError as exc:
            status = _extract_http_status(exc)
            if status in (401, 403, 404):
                logger.warning(
                    "AppData secret detection fallback: op=GET %s toolkit=%s stage=fetch reason=%s",
                    endpoint, toolkit_id, status,
                )
                self._identity_neg.set(i_key, True)
            else:
                logger.warning(
                    "AppData secret detection fallback: op=GET %s toolkit=%s stage=fetch reason=%s",
                    endpoint, toolkit_id, type(exc).__name__,
                )
                self._global_neg.set(g_key, True)
            return None
        except Exception as exc:
            logger.warning(
                "AppData secret detection fallback: op=GET %s toolkit=%s stage=fetch reason=%s",
                endpoint, toolkit_id, type(exc).__name__,
            )
            self._global_neg.set(g_key, True)
            return None

        if not isinstance(resp, dict):
            logger.warning(
                "AppData secret detection fallback: op=GET %s toolkit=%s stage=parse reason=non-dict-response",
                endpoint, toolkit_id,
            )
            self._global_neg.set(g_key, True)
            return None

        version = resp.get("version") or resp.get("pluginVersion")
        version_str: str | None = str(version) if version is not None else None
        self._version_bindings.set(g_key, version_str)

        d_key = (base_url, toolkit_id, version_str)
        found_d, cached = self._derived.get(d_key)
        if found_d:
            return cached

        # Walk all definitions
        records: dict[str, frozenset[SecretPath]] = {}
        for def_name in _DEFINITION_LOOKUP:
            schema = _extract_definition_schema(resp, def_name)
            if schema is None:
                continue
            try:
                paths = walk_secret_paths(schema, root=schema, context=f"{toolkit_id}/{def_name}")
                records[def_name] = paths
            except Exception as exc:
                logger.warning(
                    "AppData secret detection fallback: toolkit=%s stage=walk reason=%s",
                    toolkit_id, type(exc).__name__,
                )

        self._derived.set(d_key, records)
        return records


def _extract_http_status(exc: DCTClientError) -> int | None:
    """Extract HTTP status from a DCTClientError without logging its message."""
    try:
        return int(exc.args[0]) if exc.args else None
    except (ValueError, TypeError):
        # Try looking for a status attribute
        return getattr(exc, "status_code", getattr(exc, "status", None))


# Module-level cache instances
_toolkit_cache = _ToolkitSecretCache()
_object_cache: _TTLCache = _TTLCache(1024, _OBJECT_TTL_S)
_object_neg_cache: _TTLCache = _TTLCache(1024, _OBJECT_NEGATIVE_TTL_S)


def clear_caches() -> None:
    """Clear all in-memory caches. Used in tests."""
    _toolkit_cache.clear()
    _object_cache.clear()
    _object_neg_cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# expand_and_flag
# ─────────────────────────────────────────────────────────────────────────────


def _key_to_segment(key: str) -> str:
    """Render a dict key as a path segment: plain identifier or ["key"]."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]*", key):
        return key
    return f'["{key}"]'


def _expand_path(
    path_template: str,
    body_value: Any,
) -> list[tuple[str, Any]]:
    """Expand [*] and .* wildcards to concrete indices/keys.

    Returns list of (concrete_path, value_at_that_path).
    """
    segments = re.split(r"(\[\*\]|\.\*)", path_template)
    results: list[tuple[str, Any]] = [("", body_value)]

    for seg in segments:
        if seg == "[*]":
            new_results = []
            for partial_path, val in results:
                if isinstance(val, list):
                    for idx, item in enumerate(val):
                        new_results.append((f"{partial_path}[{idx}]", item))
                else:
                    # Type mismatch: scan for leaf name
                    new_results.append((partial_path, val))
            results = new_results
        elif seg == ".*":
            new_results = []
            for partial_path, val in results:
                if isinstance(val, dict):
                    for k, v in val.items():
                        new_results.append((f"{partial_path}.{_key_to_segment(k)}", v))
                else:
                    new_results.append((partial_path, val))
            results = new_results
        else:
            # Regular path segment(s)
            for part in re.split(r"\.", seg):
                if not part:
                    continue
                new_results = []
                for partial_path, val in results:
                    new_path = f"{partial_path}.{part}" if partial_path else part
                    child = val.get(part) if isinstance(val, dict) else None
                    new_results.append((new_path, child))
                results = new_results

    return results


def expand_and_flag(
    sub_object: str,
    value: Any,
    records: frozenset[SecretPath],
) -> list[FlaggedLocation]:
    """Expand wildcard paths against *value* and produce FlaggedLocation list.

    *sub_object* is the body key (e.g. "parameters") and *value* is its dict value.
    """
    flagged: list[FlaggedLocation] = []

    for sp in records:
        path = sp.path  # e.g. "nodes[*].nodePassword"

        # Determine if the field has wildcards
        has_wildcard = "[*]" in path or ".*" in path

        if has_wildcard:
            expansions = _expand_path(path, value)
            for concrete_path, leaf_val in expansions:
                if leaf_val is not None or (
                    isinstance(value, dict)
                    and _path_exists(value, concrete_path)
                ):
                    leaf_name = re.split(r"[.\[]", path)[-1].rstrip("]")
                    full_loc = f"{sub_object}.{concrete_path}" if concrete_path else sub_object
                    flagged.append(FlaggedLocation(name=leaf_name, location=full_loc))
        else:
            # No wildcard — navigate the path
            parts = path.split(".")
            node: Any = value
            parent_exists = True
            for part in parts[:-1]:
                if isinstance(node, dict):
                    node = node.get(part)
                    if node is None:
                        parent_exists = False
                        break
                else:
                    parent_exists = False
                    break

            leaf_name = parts[-1] if parts else path
            if parent_exists and isinstance(node, dict) and leaf_name in node:
                # Present — always flag
                full_loc = f"{sub_object}.{path}" if path else sub_object
                flagged.append(FlaggedLocation(name=leaf_name, location=full_loc))
            elif (
                sp.required
                and not sp.conditional
                and not has_wildcard
                and parent_exists
                and isinstance(node, dict)
            ):
                # Absent but required and non-conditional — flag
                full_loc = f"{sub_object}.{path}" if path else sub_object
                flagged.append(FlaggedLocation(name=leaf_name, location=full_loc))

    return flagged


def _path_exists(root: dict, dotted_path: str) -> bool:
    """Return True if the dotted/bracketed path exists in *root*."""
    node: Any = root
    for part in re.split(r"\.|(?=\[)", dotted_path):
        if not part:
            continue
        if part.startswith("[") and part.endswith("]"):
            idx_str = part[1:-1]
            if isinstance(node, list):
                try:
                    node = node[int(idx_str)]
                except (IndexError, ValueError):
                    return False
            else:
                return False
        elif isinstance(node, dict):
            if part not in node:
                return False
            node = node[part]
        else:
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# parse_applied / drop_applied
# ─────────────────────────────────────────────────────────────────────────────


def parse_applied(
    sensitive_applied: Any,
) -> tuple[frozenset[str], frozenset[str]]:
    """Authenticate and parse sensitive_applied.

    Returns (bare_names, location_strings). Both empty if nonce is wrong/missing.

    sensitive_applied must be a dict with:
      - "marker": the nonce string (compared against _SENSITIVE_NONCE_ENV)
      - "fields": list of str — bare names (no "." or "[") or location paths
    """
    if not isinstance(sensitive_applied, dict):
        return frozenset(), frozenset()
    marker_val = sensitive_applied.get("marker")
    # host_nonce_ok expects a dict with a "nonce" key
    if not host_nonce_ok({"nonce": marker_val}):
        return frozenset(), frozenset()

    fields = sensitive_applied.get("fields", [])
    if not isinstance(fields, list):
        return frozenset(), frozenset()

    names: set[str] = set()
    locs: set[str] = set()
    for f in fields:
        if not isinstance(f, str):
            continue
        if "." in f or "[" in f:
            locs.add(f)
        else:
            names.add(f)

    return frozenset(names), frozenset(locs)


def drop_applied(
    flagged: list[FlaggedLocation],
    names: frozenset[str],
    locations: frozenset[str],
) -> list[FlaggedLocation]:
    """Remove from *flagged* any entry satisfied by an applied name or location.

    Matching rules (any one satisfies):
    1. Exact location match
    2. Applied location equals flagged location minus its <sub_object>. prefix
       (only when exactly one flagged entry has that relative form)
    3. Applied bare name equals the leaf name

    Array index differences are NOT considered equal (EC-14).
    """
    if not names and not locations:
        return flagged

    # Build relative location → count map for rule 2
    rel_counts: dict[str, int] = {}
    for fl in flagged:
        # Relative = strip first path component
        parts = fl.location.split(".", 1)
        rel = parts[1] if len(parts) == 2 else ""
        rel_counts[rel] = rel_counts.get(rel, 0) + 1

    result = []
    for fl in flagged:
        parts = fl.location.split(".", 1)
        rel = parts[1] if len(parts) == 2 else ""

        # Rule 1: exact location
        if fl.location in locations:
            continue
        # Rule 2: relative location (unambiguous only)
        if rel in locations and rel_counts.get(rel, 0) == 1:
            continue
        # Rule 3: bare name
        if fl.name in names:
            continue
        result.append(fl)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Resolver chains (simple parsing and execution)
# ─────────────────────────────────────────────────────────────────────────────


def _resolution_budget_s() -> float:
    """Return the configured DCT_TIMEOUT as the overall resolution budget."""
    try:
        from dct_mcp_server.config.config import get_dct_config
        cfg = get_dct_config(require_key=False)
        return float(cfg.get("timeout", 30))
    except Exception:
        return 30.0


async def _execute_chain(
    client: Any,
    identity: str,
    chain_str: str,
    path_params: dict,
    body: dict,
    method_path: str,
) -> str | None:
    """Execute a single chain string and return a toolkit_id or None."""

    async def _get_object(get_path: str, current_id: str) -> dict | None:
        endpoint = get_path.replace("{id}", current_id)
        # Replace {body.<field>} references
        endpoint = re.sub(
            r"\{body\.([^}]+)\}",
            lambda m: str(body.get(m.group(1), "")),
            endpoint,
        )
        cache_key = (identity, get_path, current_id)
        found, cached = _object_cache.get(cache_key)
        if found:
            return cached
        found_neg, _ = _object_neg_cache.get(cache_key)
        if found_neg:
            return None
        try:
            resp = await client.make_request("GET", endpoint)
            if isinstance(resp, dict):
                _object_cache.set(cache_key, resp)
                return resp
        except DCTClientError as exc:
            status = _extract_http_status(exc)
            if status != 404:
                logger.warning(
                    "AppData secret detection fallback: op=GET %s stage=resolve reason=%s",
                    endpoint, status or type(exc).__name__,
                )
            _object_neg_cache.set(cache_key, True)
        except Exception as exc:
            logger.warning(
                "AppData secret detection fallback: op=GET %s stage=resolve reason=%s",
                endpoint, type(exc).__name__,
            )
            _object_neg_cache.set(cache_key, True)
        return None

    # Parse chain_str: "source > hop1 > hop2"
    # source: "body:field" or "path:param"
    steps = [s.strip() for s in chain_str.split(">")]
    if not steps:
        return None

    source_str = steps[0]
    if source_str.startswith("body:"):
        field = source_str[5:]
        current_id = body.get(field)
        if not isinstance(current_id, str) or not current_id:
            return None
        # If no hops, current_id IS the toolkit_id (e.g. body:toolkit_id)
        if len(steps) == 1:
            return current_id
    elif source_str.startswith("path:"):
        param = source_str[5:]
        current_id = path_params.get(param)
        if not isinstance(current_id, str) or not current_id:
            return None
    else:
        return None

    # Walk hops
    for hop_str in steps[1:]:
        # Split alternatives on ^
        alternatives = [a.strip() for a in hop_str.split("^")]

        result_id: str | None = None
        for alt in alternatives:
            # Extract select
            # Pattern: get_path "." select (select may contain brackets)
            # A select is present if there's a "." AFTER the last "/" in the path
            match = re.match(r"^([^.]+(?:\.[^.]+)*?)(?:\.([a-zA-Z_][a-zA-Z0-9_\[\]=$.]*))$", alt)
            if match:
                get_path_part = match.group(1).strip()
                select = match.group(2).strip()
            else:
                get_path_part = alt.strip()
                select = None

            obj = await _get_object(get_path_part, current_id)
            if obj is None:
                continue  # try next alternative

            if select is None:
                # No select: toolkit_id is from response
                tk = obj.get("toolkit_id") or obj.get("toolkitId")
                if isinstance(tk, str):
                    result_id = tk
                    break
                continue

            # Parse select
            # Could be: "field", "field[N]", "field[id=$]"
            arr_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)(?:\[(\d+|id=\$)\])?$", select)
            if not arr_match:
                continue
            field_name = arr_match.group(1)
            arr_idx = arr_match.group(2)

            field_val = obj.get(field_name)
            if arr_idx is None:
                # Plain field select — value is the next id
                if isinstance(field_val, str):
                    result_id = field_val
                    break
                # Could also be a list; take first
                if isinstance(field_val, list) and field_val:
                    result_id = field_val[0] if isinstance(field_val[0], str) else None
                    break
            elif arr_idx.isdigit():
                idx = int(arr_idx)
                if isinstance(field_val, list) and idx < len(field_val):
                    item = field_val[idx]
                    if isinstance(item, str):
                        result_id = item
                        break
            elif arr_idx == "id=$":
                # Find item in list whose "id" matches current_id
                if isinstance(field_val, list):
                    for item in field_val:
                        if isinstance(item, dict) and item.get("id") == current_id:
                            tk = item.get("toolkit_id") or item.get("toolkitId")
                            if isinstance(tk, str):
                                result_id = tk
                                break
                    if result_id:
                        break

        if result_id is None:
            return None
        current_id = result_id

    return current_id


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


async def find_flagged_connector_secrets(
    client_resolver: Callable[[], tuple[Any, str]],
    method: str,
    resolved_path: str,
    path_params: dict,
    body: dict | None,
    sensitive_applied: Any,
) -> ConnectorResult:
    """Detect AppData connector secret fields in *body* that need secure capture.

    Never raises. Returns ConnectorResult(flagged=[], covered_sub_objects=frozenset())
    on any failure (fail-open).

    Args:
        client_resolver: Callable returning (DCTAPIClient, identity_str).
        method: HTTP method string (e.g. "POST").
        resolved_path: Concrete path with {params} already substituted.
        path_params: Dict of path parameter values (e.g. {"dsourceId": "ds-1"}).
        body: The parsed request body dict, or None.
        sensitive_applied: The sensitive_applied payload from the caller.
    """
    try:
        return await _find_flagged_inner(
            client_resolver, method, resolved_path, path_params, body, sensitive_applied
        )
    except Exception as exc:
        logger.warning(
            "AppData secret detection fallback: stage=budget reason=%s", type(exc).__name__
        )
        return ConnectorResult()


async def _find_flagged_inner(
    client_resolver: Callable[[], tuple[Any, str]],
    method: str,
    resolved_path: str,
    path_params: dict,
    body: dict | None,
    sensitive_applied: Any,
) -> ConnectorResult:
    # Step 1: Match operation
    op = match_appdata_operation(method, resolved_path)
    if op is None:
        return ConnectorResult()

    # Step 2: Keep only present sub-objects
    if body is None:
        return ConnectorResult()
    present_sub_objects = {
        k: v for k, v in op.sub_objects.items()
        if isinstance(body.get(k), dict)
    }
    if not present_sub_objects:
        return ConnectorResult()

    # Step 3: Resolve client and identity (lazy — only now that we have work)
    try:
        client, identity = client_resolver()
    except Exception as exc:
        logger.warning(
            "AppData secret detection fallback: op=%s %s stage=resolve reason=%s",
            method, resolved_path, type(exc).__name__,
        )
        return ConnectorResult()

    _, toolkit_path = load_appdata_operations()
    if not toolkit_path:
        logger.warning(
            "AppData secret detection fallback: op=%s %s stage=resolve reason=no-toolkit-path",
            method, resolved_path,
        )
        return ConnectorResult()

    method_path = f"{method} {resolved_path}"

    async def _run_with_budget() -> ConnectorResult:
        # Step 4: Resolve toolkit ids from all chains concurrently
        chain_tasks = [
            _execute_chain(client, identity, chain, path_params, body or {}, method_path)
            for chain in op.chains
        ]
        chain_results = await asyncio.gather(*chain_tasks, return_exceptions=True)
        toolkit_ids: set[str] = set()
        for r in chain_results:
            if isinstance(r, str) and r:
                toolkit_ids.add(r)
            elif isinstance(r, Exception):
                logger.warning(
                    "AppData secret detection fallback: op=%s stage=resolve reason=%s",
                    method_path, type(r).__name__,
                )

        if not toolkit_ids:
            return ConnectorResult()

        # Step 5: Fetch toolkit schema for each toolkit id concurrently
        fetch_tasks = [
            _toolkit_cache.get(client, identity, tid, toolkit_path, method_path)
            for tid in toolkit_ids
        ]
        fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        # Step 6 + 7: For each covered sub-object, union records across toolkits
        sub_obj_records: dict[str, frozenset[SecretPath]] = {}
        covered: set[str] = set()

        for tid, result in zip(toolkit_ids, fetch_results):
            if isinstance(result, dict):
                for sub_obj_name, def_name in present_sub_objects.items():
                    if def_name in result:
                        covered.add(sub_obj_name)
                        existing = sub_obj_records.get(sub_obj_name, frozenset())
                        sub_obj_records[sub_obj_name] = existing | result[def_name]
            elif isinstance(result, Exception):
                logger.warning(
                    "AppData secret detection fallback: op=%s toolkit=unknown stage=fetch reason=%s",
                    method_path, type(result).__name__,
                )

        # Parse applied fields
        applied_names, applied_locs = parse_applied(sensitive_applied)

        # For each covered sub-object: expand, flag, drop applied
        all_flagged: list[FlaggedLocation] = []
        for sub_obj_name in covered:
            records = sub_obj_records.get(sub_obj_name, frozenset())
            sub_val = body.get(sub_obj_name, {})
            flagged = expand_and_flag(sub_obj_name, sub_val, records)
            flagged = drop_applied(flagged, applied_names, applied_locs)
            all_flagged.extend(flagged)

        return ConnectorResult(
            flagged=all_flagged,
            covered_sub_objects=frozenset(covered),
        )

    budget = _resolution_budget_s()
    try:
        return await asyncio.wait_for(_run_with_budget(), timeout=budget)
    except asyncio.TimeoutError:
        logger.warning(
            "AppData secret detection fallback: op=%s stage=budget reason=timeout",
            method_path,
        )
        return ConnectorResult()
