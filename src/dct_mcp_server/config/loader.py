"""
Configuration Loader for DCT MCP Server

This module provides functions to load and manage toolset configurations
from text-based configuration files. It eliminates the need for code changes
when adding new APIs or modifying toolsets.

Configuration Files:
- config/toolsets/*.txt: Toolset definitions (APIs per toolset)
- config/mappings/manual_confirmation.txt: Confirmation rules for destructive operations
"""

import os
import re
import logging
from pathlib import Path
from typing import Callable, Dict, List, Any, Tuple, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Configuration directories
CONFIG_DIR = Path(__file__).parent
TOOLSETS_DIR = CONFIG_DIR / "toolsets"
MAPPINGS_DIR = CONFIG_DIR / "mappings"


# ============================================================================
# TOOLSET LOADING FUNCTIONS
# ============================================================================


@lru_cache(maxsize=10)
def load_toolset_apis(toolset_name: str) -> Tuple[Dict[str, str], ...]:
    """
    Load all APIs for a toolset from text file.

    Args:
        toolset_name: Name of the toolset (e.g., "self_service")

    Returns:
        Tuple of dicts: ({"method": "GET", "path": "/vdbs/{id}", "action": "get"}, ...)

    Raises:
        ValueError: If toolset file doesn't exist
    """
    toolset_file = TOOLSETS_DIR / f"{toolset_name}.txt"

    if not toolset_file.exists():
        raise ValueError(f"Unknown toolset: {toolset_name}")

    apis = []

    with open(toolset_file, "r") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Handle inheritance
            if line.startswith("@inherit:"):
                parent_toolset = line.split(":")[1].strip()
                # Validate parent exists before loading
                parent_file = TOOLSETS_DIR / f"{parent_toolset}.txt"
                if not parent_file.exists():
                    raise ValueError(
                        f"Toolset '{toolset_name}' inherits from '{parent_toolset}' "
                        f"but parent toolset file does not exist: {parent_file}"
                    )
                parent_apis = load_toolset_apis(parent_toolset)
                apis.extend(parent_apis)
                continue

            # Parse METHOD|/path|action format
            parts = line.split("|")
            if len(parts) >= 3:
                apis.append(
                    {
                        "method": parts[0].strip(),
                        "path": parts[1].strip(),
                        "action": parts[2].strip(),
                    }
                )

    return tuple(apis)


@lru_cache(maxsize=10)
def load_toolset_grouped_apis(toolset_name: str) -> Dict[str, Dict[str, Any]]:
    """
    Load APIs for a toolset grouped by tool name from # TOOL headers.

    Parses toolset files that have structure like:
        # TOOL 1: vdb_tool - VDB Operations
        POST|/vdbs/search|search_vdbs
        GET|/vdbs/{vdbId}|get_vdb
        # TOOL 2: dsource_tool - dSource Operations
        POST|/dsources/search|search_dsources

    Args:
        toolset_name: Name of the toolset (e.g., "continuous_data_admin")

    Returns:
        Dict mapping tool_name to {description, apis: [{method, path, action}]}

    Raises:
        ValueError: If toolset file doesn't exist
    """
    toolset_file = TOOLSETS_DIR / f"{toolset_name}.txt"

    if not toolset_file.exists():
        raise ValueError(f"Unknown toolset: {toolset_name}")

    grouped = {}
    current_tool = None
    current_description = ""

    with open(toolset_file, "r") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Parse TOOL header: # TOOL N: tool_name - Description
            if line.startswith("# TOOL") and ":" in line:
                # Extract tool name and description
                # Format: # TOOL 1: vdb_tool - VDB Operations
                after_colon = line.split(":", 1)[
                    1
                ].strip()  # "vdb_tool - VDB Operations"
                if " - " in after_colon:
                    current_tool, current_description = after_colon.split(" - ", 1)
                    current_tool = current_tool.strip()
                    current_description = current_description.strip()
                else:
                    current_tool = after_colon.strip()
                    current_description = ""

                if current_tool and current_tool not in grouped:
                    grouped[current_tool] = {
                        "description": current_description,
                        "apis": [],
                    }
                continue

            # Skip other comments
            if line.startswith("#"):
                continue

            # Handle inheritance - load parent's grouped APIs
            if line.startswith("@inherit:"):
                parent_toolset = line.split(":")[1].strip()
                parent_file = TOOLSETS_DIR / f"{parent_toolset}.txt"
                if not parent_file.exists():
                    raise ValueError(
                        f"Toolset '{toolset_name}' inherits from '{parent_toolset}' "
                        f"but parent toolset file does not exist: {parent_file}"
                    )
                parent_grouped = load_toolset_grouped_apis(parent_toolset)
                for tool_name, tool_data in parent_grouped.items():
                    if tool_name not in grouped:
                        grouped[tool_name] = {
                            "description": tool_data["description"],
                            "apis": [],
                        }
                    grouped[tool_name]["apis"].extend(tool_data["apis"])
                continue

            # Parse METHOD|/path|action format
            parts = line.split("|")
            if len(parts) >= 3 and current_tool:
                api_entry = {
                    "method": parts[0].strip(),
                    "path": parts[1].strip(),
                    "action": parts[2].strip(),
                }
                grouped[current_tool]["apis"].append(api_entry)

    return grouped


def load_toolset_metadata(toolset_name: str) -> Optional[Dict[str, Any]]:
    """
    Load toolset metadata by parsing headers from the toolset file.

    Each toolset file has headers like:
        # Self Service Toolset - 6 Tools
        # Description: Perform classic Self Service activities
        # Target users: Developers, QA engineers who need to work with VDBs

    Args:
        toolset_name: Name of the toolset

    Returns:
        Dict with name, description, tool_count, primary_use_case or None if not found
    """
    toolset_file = TOOLSETS_DIR / f"{toolset_name}.txt"

    if not toolset_file.exists():
        return None

    metadata = {"name": toolset_name}
    tool_count = 0

    with open(toolset_file, "r") as f:
        for line in f:
            line = line.strip()

            if line.startswith("# Description:"):
                metadata["description"] = line.replace("# Description:", "").strip()
            elif line.startswith("# Target users:"):
                metadata["primary_use_case"] = line.replace(
                    "# Target users:", ""
                ).strip()
            elif line.startswith("# TOOL") and ":" in line:
                tool_count += 1

    metadata["tool_count"] = tool_count
    return metadata


def load_all_toolsets_metadata() -> Dict[str, Dict[str, Any]]:
    """
    Load metadata for all available toolsets by scanning the toolsets directory.

    Returns:
        Dict mapping toolset names to their metadata
    """
    toolsets = {}

    for toolset_file in TOOLSETS_DIR.glob("*.txt"):
        toolset_name = toolset_file.stem  # e.g., "self_service"
        metadata = load_toolset_metadata(toolset_name)
        if metadata:
            toolsets[toolset_name] = metadata

    return toolsets


# ============================================================================
# MANUAL CONFIRMATION FUNCTIONS
# ============================================================================


@lru_cache(maxsize=1)
def load_manual_confirmation_rules() -> Tuple[Dict[str, Any], ...]:
    """
    Load manual confirmation rules.

    Format: METHOD|path_pattern|confirmation_level|message_template

    Returns:
        Tuple of rule dicts with method, path_pattern, level, and message
    """
    rules = []
    config_file = MAPPINGS_DIR / "manual_confirmation.txt"

    if not config_file.exists():
        logger.warning(f"Manual confirmation file not found: {config_file}")
        return tuple(rules)

    with open(config_file, "r") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) >= 4:
                rules.append(
                    {
                        "method": parts[0].strip(),
                        "path_pattern": parts[1].strip(),
                        "level": parts[2].strip(),
                        "message": parts[3].strip(),
                    }
                )

    return tuple(rules)


def _path_matches(path: str, pattern: str) -> bool:
    """
    Check if a path matches a pattern with path parameters.

    Args:
        path: Actual API path (e.g., "/vdbs/vdb-123/delete")
        pattern: Pattern with placeholders (e.g., "/vdbs/{vdbId}/delete")

    Returns:
        True if path matches pattern
    """
    # Convert path parameters to regex
    regex_pattern = re.sub(r"\{[^}]+\}", r"[^/]+", pattern)
    regex_pattern = f"^{regex_pattern}$"
    return bool(re.match(regex_pattern, path))


def _is_destructive_delete(method: str, path: str) -> bool:
    """Return True for destructive delete operations.

    Covers any HTTP DELETE, plus the DCT convention of POST to a ``.../delete``
    action path (e.g. ``/vdbs/{vdbId}/delete``). Used as a safety net so a delete
    never executes without confirmation just because it lacks an explicit rule in
    manual_confirmation.txt.
    """
    m = (method or "").upper()
    if m == "DELETE":
        return True
    if m == "POST" and path.rstrip("/").endswith("/delete"):
        return True
    return False


@lru_cache(maxsize=1)
def _load_read_exclusions() -> frozenset:
    """
    Load read exclusion path patterns from read_exclusions.txt.

    Returns:
        frozenset of path patterns that are safe reads and should not be
        gated by the keyword fallback confirmation resolver.
    """
    exclusions_file = MAPPINGS_DIR / "read_exclusions.txt"

    if not exclusions_file.exists():
        logger.warning(f"Read exclusions file not found: {exclusions_file}")
        return frozenset()

    patterns = []
    with open(exclusions_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)

    return frozenset(patterns)


@lru_cache(maxsize=1)
def load_server_instructions() -> str:
    """
    Load the cross-cutting vocabulary and domain-model guidance passed to the
    MCP client as the server's ``instructions`` (PPM-1129).

    Source is ``config/server_instructions.md`` unless the
    ``DCT_SERVER_INSTRUCTIONS`` environment variable names another file.

    Returns:
        The instructions text, or an empty string if no file is available.
        A missing or unreadable file is never fatal: the server starts
        without vocabulary guidance rather than failing.
    """
    override = (os.getenv("DCT_SERVER_INSTRUCTIONS") or "").strip() or None
    instructions_file = (
        Path(override) if override else CONFIG_DIR / "server_instructions.md"
    )

    if not instructions_file.is_file():
        logger.warning(
            f"Server instructions file not found or is not a file: {instructions_file}"
        )
        return ""

    try:
        with open(instructions_file, "r", encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Could not read server instructions {instructions_file}: {e}")
        return ""
    # HTML comments are for maintainers (provenance, reviewer notes). Clients keep
    # only the first few thousand characters of the instructions, so none of that
    # may be sent to the model.
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# Optional guard directives a vocabulary.txt line may carry after the term
# pair. Each value is a comma-separated, case-insensitive word list; an entry
# of the form "@name" expands to the words of an "@signals name=..." line.
_VOCABULARY_GUARD_KEYS = (
    "skip_if_preceded_by",
    "skip_if_followed_by",
    "only_if_text_mentions",
    "skip_if_text_mentions",
)


def _expand_signal_words(words: str, signals: Dict[str, frozenset]) -> frozenset:
    expanded: set = set()
    for word in (w.strip().lower() for w in words.split(",")):
        if not word:
            continue
        if word.startswith("@"):
            if word[1:] not in signals:
                logger.warning(f"Unknown vocabulary signal set {word!r}")
                continue
            expanded |= signals[word[1:]]
        else:
            expanded.add(word)
    return frozenset(expanded)


@lru_cache(maxsize=1)
def load_vocabulary_rules() -> Tuple[Dict[str, Any], ...]:
    """
    Load the internal-to-canonical term rules from mappings/vocabulary.txt.

    Used to translate upstream text (raw DCT error bodies, OpenAPI summaries)
    into customer-facing terminology before it is shown to a user (PPM-1129).

    Line formats::

        @signals name=word,word,...
        internal|canonical[|guard=word,word...]...

    where ``guard`` is one of ``skip_if_preceded_by``, ``skip_if_followed_by``,
    ``only_if_text_mentions`` or ``skip_if_text_mentions``, and a guard word
    of the form ``@name`` expands to a previously declared signal set. Several
    lines may share an internal term; the first one whose text conditions hold
    wins.

    Returns:
        Tuple of rule dicts with keys ``internal``, ``canonical`` and one
        frozenset per guard key, ordered longest-internal-first (stable, so
        file order is kept between lines for the same term). Empty if the
        file is absent.
    """
    vocab_file = MAPPINGS_DIR / "vocabulary.txt"

    if not vocab_file.exists():
        logger.warning(f"Vocabulary file not found: {vocab_file}")
        return ()

    rules: List[Dict[str, Any]] = []
    signals: Dict[str, frozenset] = {}
    try:
        with open(vocab_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("@signals"):
                    name, _, words = line[len("@signals") :].partition("=")
                    signals[name.strip().lower()] = _expand_signal_words(words, signals)
                    continue
                parts = line.split("|")
                if len(parts) < 2:
                    continue
                internal, canonical = parts[0].strip(), parts[1].strip()
                if not (internal and canonical):
                    continue
                rule: Dict[str, Any] = {
                    "internal": internal,
                    "canonical": canonical,
                    **{key: frozenset() for key in _VOCABULARY_GUARD_KEYS},
                }
                for directive in parts[2:]:
                    key, _, words = directive.partition("=")
                    key = key.strip()
                    if key not in _VOCABULARY_GUARD_KEYS:
                        logger.warning(
                            f"Unknown vocabulary guard {key!r} for term {internal!r}"
                        )
                        continue
                    rule[key] = _expand_signal_words(words, signals)
                rules.append(rule)
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Could not read vocabulary rules {vocab_file}: {e}")
        return ()

    # Longest first: "delphix engine" must win over a bare "engine" entry.
    rules.sort(key=lambda rule: len(rule["internal"]), reverse=True)
    return tuple(rules)


@lru_cache(maxsize=1)
def load_vocabulary_map() -> Tuple[Tuple[str, str], ...]:
    """
    The vocabulary rules as plain (internal_term, canonical_term) pairs.

    Guard directives are dropped; see :func:`load_vocabulary_rules` for the
    full rules that :func:`~dct_mcp_server.tools.core.vocabulary.to_canonical`
    applies.
    """
    return tuple((r["internal"], r["canonical"]) for r in load_vocabulary_rules())


def _is_read_exclusion(path: str) -> bool:
    """
    Check if a path matches any read exclusion pattern.

    Args:
        path: API endpoint path to check

    Returns:
        True if path is a known safe read and should not be confirmation-gated
    """
    patterns = _load_read_exclusions()
    for pattern in patterns:
        if _path_matches(path, pattern):
            return True
        # Also check prefix match for patterns without trailing wildcards
        if path.startswith(pattern):
            return True
    return False


def get_confirmation_for_operation(method: str, path: str) -> Dict[str, Any]:
    """
    Get confirmation requirements for an API operation.

    Args:
        method: HTTP method (GET, POST, DELETE, etc.)
        path: API endpoint path

    Returns:
        Dict with level, message, conditional flag, and threshold_days
    """
    rules = load_manual_confirmation_rules()

    for rule in rules:
        # Check method match (wildcard * matches any method)
        if rule["method"] != "*" and rule["method"] != method:
            continue

        # Check path match
        if _path_matches(path, rule["path_pattern"]):
            level = rule["level"]
            conditional = ":" in level
            level_parts = level.split(":") if conditional else [level]
            level_name = level_parts[0]
            threshold_N = (
                int(level_parts[1]) if conditional and len(level_parts) > 1 else None
            )
            threshold_T = (
                int(level_parts[2]) if conditional and len(level_parts) > 2 else None
            )

            return {
                "level": level_name,
                "message": rule["message"],
                "conditional": conditional,
                "threshold_days": threshold_N,
                "threshold_T": threshold_T,
                # The matched rule's path template (e.g. "/vdbs/{vdbId}/refresh_by_snapshot").
                # Used to key velocity counters and standing grants per operation-type
                # rather than per resolved resource.
                "path_pattern": rule["path_pattern"],
            }

    # Safety net: a destructive delete must never run unconfirmed just because
    # it has no explicit rule above. Explicit rules (matched in the loop) still
    # take precedence and may set a different level or a tailored message.
    if _is_destructive_delete(method, path):
        return {
            "level": "manual",
            "message": (
                f"This is a destructive delete operation ({method} {path}). "
                "Please confirm before proceeding — this action cannot be undone."
            ),
            "conditional": False,
            "threshold_days": None,
            "threshold_T": None,
            "path_pattern": path,
        }

    # Keyword fallback — only when DCT_CONFIRMATION_FALLBACK=keyword and path is not a read exclusion
    _fallback = os.environ.get("DCT_CONFIRMATION_FALLBACK", "keyword").lower()
    if _fallback == "keyword" and not _is_read_exclusion(path):
        # Import here to avoid circular imports (dynamic_confirmation imports from loader)
        try:
            from dct_mcp_server.tools.core.dynamic_confirmation import (
                get_confirmation_for_operation_dynamic,
            )

            dynamic_result = get_confirmation_for_operation_dynamic(method, path)
            if dynamic_result.get("level", "none") != "none":
                # Keyword fallback has no rule template; key on the resolved path.
                dynamic_result.setdefault("path_pattern", path)
                return dynamic_result
        except ImportError:
            pass

    # No matching rule - no confirmation needed
    return {
        "level": "none",
        "message": None,
        "conditional": False,
        "threshold_days": None,
        "threshold_T": None,
        "path_pattern": path,
    }


def requires_confirmation(method: str, path: str) -> bool:
    """
    Quick check if an operation requires any form of confirmation.

    Args:
        method: HTTP method
        path: API endpoint path

    Returns:
        True if confirmation is required
    """
    confirmation = get_confirmation_for_operation(method, path)
    # batch_check is a dynamic-mode velocity level evaluated by the dynamic
    # execute gate against a live per-identity counter; on its own (static path)
    # it does not require per-call confirmation.
    return confirmation["level"] not in ("none", "batch_check")


# ============================================================================
# TOOLSET SELECTION FUNCTIONS
# ============================================================================


def get_available_toolsets() -> List[str]:
    """
    Get list of available toolsets by scanning the toolsets directory.

    Returns:
        List of toolset names (e.g., ["self_service", "platform_admin"])
    """
    return [f.stem for f in TOOLSETS_DIR.glob("*.txt")]


def get_configured_toolset() -> str:
    """
    Get the configured toolset from environment variable.

    Environment Variable: DCT_TOOLSET

    Returns:
        Toolset name or 'dynamic' as default

    Raises:
        ValueError: If invalid toolset name specified
    """
    toolset = os.environ.get("DCT_TOOLSET", "dynamic").lower().strip()

    if toolset == "dynamic":
        return toolset

    available = get_available_toolsets()
    if toolset not in available:
        raise ValueError(
            f"Invalid toolset: {toolset}. Valid values: dynamic, {', '.join(available)}"
        )

    return toolset


def is_dynamic_mode() -> bool:
    """
    Check if server is running in dynamic 2-tool mode.

    Returns:
        True if DCT_TOOLSET=dynamic
    """
    return get_configured_toolset() == "dynamic"


# ============================================================================
# TOOLSET TOOLS EXTRACTION
# ============================================================================


def get_tools_for_toolset(toolset_name: str) -> List[Dict[str, Any]]:
    """
    Get list of tools available in a toolset with their actions.

    Uses the # TOOL X: headers from the toolset file for accurate grouping.

    Args:
        toolset_name: Name of the toolset

    Returns:
        List of tool dicts with name, description, and actions
    """
    # Use the grouped API loader that parses # TOOL headers
    grouped_apis = load_toolset_grouped_apis(toolset_name)

    # Build result list
    tools = []
    for tool_name, tool_data in grouped_apis.items():
        actions = [api["action"] for api in tool_data.get("apis", [])]
        tool_info = {
            "name": tool_name,
            "description": tool_data.get("description", ""),
            "actions": sorted(set(actions)),  # Remove duplicates and sort
        }
        tools.append(tool_info)

    return sorted(tools, key=lambda t: t["name"])


def get_modules_for_toolset(toolset_name: str) -> List[str]:
    """
    Get the list of tool module names required for a toolset.

    This maps toolset logical tools to their implementation modules.
    Used by register_all_tools to filter which modules to load.

    Args:
        toolset_name: Name of the toolset

    Returns:
        List of module names (e.g., ["dataset_endpoints_tool", "job_endpoints_tool"])
    """
    # Mapping from logical tool names to implementation modules
    # Based on which module implements APIs for which path patterns
    TOOL_TO_MODULE = {
        # Dataset operations (vdb, dsource, snapshot, bookmark, vdb-group, timeline, source)
        "vdb_tool": "dataset_endpoints_tool",
        "vdb_group_tool": "dataset_endpoints_tool",
        "dsource_tool": "dataset_endpoints_tool",
        "snapshot_tool": "dataset_endpoints_tool",
        "bookmark_tool": "dataset_endpoints_tool",
        "source_tool": "dataset_endpoints_tool",
        "data_connection_tool": "dataset_endpoints_tool",
        "data_tool": "dataset_endpoints_tool",  # Merged tool
        "snapshot_bookmark_tool": "dataset_endpoints_tool",  # Merged tool
        "timeline_tool": "dataset_endpoints_tool",
        # Job operations
        "job_tool": "job_endpoints_tool",
        # Environment operations
        "environment_tool": "environment_endpoints_tool",
        "environment_source_tool": "environment_endpoints_tool",  # Merged tool
        # Connector schema operations
        "connector_schema_tool": "environment_endpoints_tool",
        # Engine operations
        "engine_tool": "engine_endpoints_tool",
        # Compliance operations
        "masking_tool": "compliance_endpoints_tool",
        "connector_tool": "compliance_endpoints_tool",
        "execution_tool": "compliance_endpoints_tool",
        # Reports operations
        "reporting_tool": "reports_endpoints_tool",
        # IAM operations (if we have the module)
        "iam_tool": "iam_endpoints_tool",
        "tag_tool": "iam_endpoints_tool",
        # Template operations (if we have the module)
        "vdb_template_tool": "template_endpoints_tool",
        "hook_template_tool": "template_endpoints_tool",
        # Policy operations (if we have the module)
        "virtualization_policy_tool": "policy_endpoints_tool",
        "replication_tool": "policy_endpoints_tool",
        # Platform admin merged tool
        "admin_platform_tool": "admin_endpoints_tool",
        # Instance tools (CDB/vCDB)
        "instance_tool": "misc_endpoints_tool",
        # Dynamic 2-tool mode tools (DCT_TOOLSET=dynamic)
        "discovery": "dynamic",
        "execute": "dynamic",
    }

    # Get the tools used by this toolset
    tools = get_tools_for_toolset(toolset_name)
    tool_names = [t["name"] for t in tools]

    # Map to modules
    modules = set()
    for tool_name in tool_names:
        if tool_name in TOOL_TO_MODULE:
            modules.add(TOOL_TO_MODULE[tool_name])
        else:
            logger.warning(f"No module mapping for tool: {tool_name}")

    return list(modules)


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================


# Hook registry: functions to call when clear_cache() resets loader caches.
# Keys are fully-qualified hook names (e.g. "dct_mcp_server.tools.core.vocabulary.clear_hook").
# Re-registering with the same name replaces the old entry, so a module reload
# never leaves a stale hook pointing at old cached-function objects.
_CACHE_CLEAR_HOOKS: Dict[str, Callable[[], None]] = {}


def register_cache_clear_hook(name: str, fn: Callable[[], None]) -> None:
    """Register (or replace) a cache-clear hook.

    ``name`` is a stable qualified string that uniquely identifies the hook
    (e.g. ``"dct_mcp_server.tools.core.vocabulary.clear_hook"``). If a hook
    with the same name is already registered it is replaced, so a module
    reload never leaves two copies of the same hook in the list.

    Args:
        name: Unique qualified name for this hook.
        fn:   Zero-argument callable; called at the end of ``clear_cache()``.
    """
    _CACHE_CLEAR_HOOKS[name] = fn


def clear_cache():
    """
    Clear all cached configuration data.

    Call this if configuration files change during runtime.
    Registered hooks (e.g. vocabulary.py's translator caches) are called
    after the loader caches are cleared, so the next rule-load reads the file
    fresh before the translator re-compiles.
    """
    load_toolset_apis.cache_clear()
    load_toolset_grouped_apis.cache_clear()
    load_manual_confirmation_rules.cache_clear()
    _load_read_exclusions.cache_clear()
    load_server_instructions.cache_clear()
    load_vocabulary_map.cache_clear()
    load_vocabulary_rules.cache_clear()
    logger.info("Configuration cache cleared")
    for hook_name, hook_fn in list(_CACHE_CLEAR_HOOKS.items()):
        try:
            hook_fn()
        except Exception as e:
            logger.warning(f"Cache-clear hook {hook_name!r} raised: {e}", exc_info=True)


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================


def validate_toolset_config(toolset_name: str) -> List[str]:
    """
    Validate a toolset configuration file.

    Args:
        toolset_name: Name of the toolset to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    try:
        apis = load_toolset_apis(toolset_name)

        if not apis:
            errors.append(f"Toolset '{toolset_name}' has no APIs defined")

    except ValueError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"Error loading toolset: {e}")

    return errors


def validate_all_configs() -> Dict[str, List[str]]:
    """
    Validate all configuration files.

    Returns:
        Dict mapping config names to list of errors
    """
    results = {}

    # Validate each toolset
    for toolset_name in get_available_toolsets():
        errors = validate_toolset_config(toolset_name)
        if errors:
            results[f"toolset:{toolset_name}"] = errors

    # Validate confirmation rules
    try:
        rules = load_manual_confirmation_rules()
        if not rules:
            results["manual_confirmation.txt"] = ["No confirmation rules defined"]
    except Exception as e:
        results["manual_confirmation.txt"] = [str(e)]

    return results
