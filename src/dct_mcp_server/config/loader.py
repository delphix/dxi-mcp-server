"""
Configuration Loader for DCT MCP Server

This module provides functions to load and manage toolset configurations
from text-based configuration files. It eliminates the need for code changes
when adding new APIs or modifying toolsets.

Configuration Files:
- config/toolsets/*.txt: Toolset definitions (APIs per toolset)
- config/mappings/tool_grouping.txt: How APIs are grouped into tools
- config/mappings/manual_confirmation.txt: Confirmation rules for destructive operations
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Configuration directories
CONFIG_DIR = Path(__file__).parent
TOOLSETS_DIR = CONFIG_DIR / "toolsets"
MAPPINGS_DIR = CONFIG_DIR / "mappings"

# Meta-tools that are always available in auto mode
META_TOOLS = ["list_available_toolsets", "get_toolset_tools", "enable_toolset"]


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
    
    with open(toolset_file, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Handle inheritance
            if line.startswith('@inherit:'):
                parent_toolset = line.split(':')[1].strip()
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
            parts = line.split('|')
            if len(parts) >= 3:
                apis.append({
                    "method": parts[0].strip(),
                    "path": parts[1].strip(),
                    "action": parts[2].strip()
                })
    
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
    
    with open(toolset_file, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Parse TOOL header: # TOOL N: tool_name - Description
            if line.startswith('# TOOL') and ':' in line:
                # Extract tool name and description
                # Format: # TOOL 1: vdb_tool - VDB Operations
                after_colon = line.split(':', 1)[1].strip()  # "vdb_tool - VDB Operations"
                if ' - ' in after_colon:
                    current_tool, current_description = after_colon.split(' - ', 1)
                    current_tool = current_tool.strip()
                    current_description = current_description.strip()
                else:
                    current_tool = after_colon.strip()
                    current_description = ""
                
                if current_tool and current_tool not in grouped:
                    grouped[current_tool] = {
                        "description": current_description,
                        "apis": []
                    }
                continue
            
            # Skip other comments
            if line.startswith('#'):
                continue
            
            # Handle inheritance - load parent's grouped APIs
            if line.startswith('@inherit:'):
                parent_toolset = line.split(':')[1].strip()
                parent_file = TOOLSETS_DIR / f"{parent_toolset}.txt"
                if not parent_file.exists():
                    raise ValueError(
                        f"Toolset '{toolset_name}' inherits from '{parent_toolset}' "
                        f"but parent toolset file does not exist: {parent_file}"
                    )
                parent_grouped = load_toolset_grouped_apis(parent_toolset)
                for tool_name, tool_data in parent_grouped.items():
                    if tool_name not in grouped:
                        grouped[tool_name] = {"description": tool_data["description"], "apis": []}
                    grouped[tool_name]["apis"].extend(tool_data["apis"])
                continue
            
            # Parse METHOD|/path|action format
            parts = line.split('|')
            if len(parts) >= 3 and current_tool:
                api_entry = {
                    "method": parts[0].strip(),
                    "path": parts[1].strip(),
                    "action": parts[2].strip()
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
    
    with open(toolset_file, 'r') as f:
        for line in f:
            line = line.strip()
            
            if line.startswith('# Description:'):
                metadata["description"] = line.replace('# Description:', '').strip()
            elif line.startswith('# Target users:'):
                metadata["primary_use_case"] = line.replace('# Target users:', '').strip()
            elif line.startswith('# TOOL') and ':' in line:
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
# TOOL GROUPING FUNCTIONS
# ============================================================================

@lru_cache(maxsize=1)
def load_tool_grouping() -> Dict[str, Dict[str, Any]]:
    """
    Load tool grouping configuration.
    
    Format: tool_name|base_path_pattern(s)|description
    
    Returns:
        Dict mapping tool names to their patterns and descriptions
    """
    grouping = {}
    config_file = MAPPINGS_DIR / "tool_grouping.txt"
    
    if not config_file.exists():
        logger.warning(f"Tool grouping file not found: {config_file}")
        return grouping
    
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('|')
            if len(parts) >= 2:
                tool_name = parts[0].strip()
                patterns = [p.strip() for p in parts[1].split(',')]
                description = parts[2].strip() if len(parts) > 2 else ""
                
                grouping[tool_name] = {
                    "patterns": patterns,
                    "description": description
                }
    
    return grouping


def get_tool_for_api(api_path: str) -> str:
    """
    Determine which tool an API belongs to based on path patterns.
    
    Args:
        api_path: API endpoint path (e.g., "/vdbs/{vdbId}")
        
    Returns:
        Tool name that handles this API, or "unknown_tool" if no match
    """
    grouping = load_tool_grouping()
    
    for tool_name, config in grouping.items():
        for pattern in config["patterns"]:
            # Normalize paths for comparison
            normalized_path = api_path.split('{')[0].rstrip('/')
            normalized_pattern = pattern.rstrip('/')
            
            if normalized_path.startswith(normalized_pattern):
                return tool_name
    
    return "unknown_tool"


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
    
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('|')
            if len(parts) >= 4:
                rules.append({
                    "method": parts[0].strip(),
                    "path_pattern": parts[1].strip(),
                    "level": parts[2].strip(),
                    "message": parts[3].strip()
                })
    
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
    regex_pattern = re.sub(r'\{[^}]+\}', r'[^/]+', pattern)
    regex_pattern = f"^{regex_pattern}$"
    return bool(re.match(regex_pattern, path))


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
            
            return {
                "level": level.split(":")[0] if conditional else level,
                "message": rule["message"],
                "conditional": conditional,
                "threshold_days": int(level.split(":")[1]) if conditional else None
            }
    
    # No matching rule - no confirmation needed
    return {"level": "none", "message": None, "conditional": False, "threshold_days": None}


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
    return confirmation["level"] != "none"


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
        Toolset name or 'self_service' as default
        
    Raises:
        ValueError: If invalid toolset name specified
    """
    toolset = os.environ.get("DCT_TOOLSET", "self_service").lower().strip()
    
    if toolset == "auto":
        return "auto"
    
    available = get_available_toolsets()
    if toolset not in available:
        raise ValueError(
            f"Invalid toolset: {toolset}. "
            f"Valid values: auto, {', '.join(available)}"
        )
    
    return toolset


def is_auto_mode() -> bool:
    """
    Check if server is running in auto (dynamic discovery) mode.
    
    Returns:
        True if DCT_TOOLSET=auto
    """
    return get_configured_toolset() == "auto"


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
            "actions": sorted(set(actions))  # Remove duplicates and sort
        }
        tools.append(tool_info)
    
    return sorted(tools, key=lambda t: t["name"])


def get_apis_grouped_by_tool(toolset_name: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Get APIs grouped by their owning tool.
    
    Args:
        toolset_name: Name of the toolset
        
    Returns:
        Dict mapping tool names to list of API definitions
    """
    apis = load_toolset_apis(toolset_name)
    
    grouped: Dict[str, List[Dict[str, str]]] = {}
    
    for api in apis:
        tool_name = get_tool_for_api(api["path"])
        if tool_name not in grouped:
            grouped[tool_name] = []
        grouped[tool_name].append(dict(api))
    
    return grouped


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
        # Dataset operations (vdb, dsource, snapshot, bookmark, vdb-group, timeflow, source)
        "vdb_tool": "dataset_endpoints_tool",
        "vdb_group_tool": "dataset_endpoints_tool",
        "dsource_tool": "dataset_endpoints_tool",
        "snapshot_tool": "dataset_endpoints_tool",
        "bookmark_tool": "dataset_endpoints_tool",
        "source_tool": "dataset_endpoints_tool",
        "data_connection_tool": "dataset_endpoints_tool",
        "data_tool": "dataset_endpoints_tool",  # Merged tool
        "snapshot_bookmark_tool": "dataset_endpoints_tool",  # Merged tool
        
        # Job operations
        "job_tool": "job_endpoints_tool",
        
        # Environment operations
        "environment_tool": "environment_endpoints_tool",
        "environment_source_tool": "environment_endpoints_tool",  # Merged tool
        
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
        "database_template_tool": "template_endpoints_tool",
        "hook_template_tool": "template_endpoints_tool",
        
        # Policy operations (if we have the module)
        "virtualization_policy_tool": "policy_endpoints_tool",
        "replication_tool": "policy_endpoints_tool",
        
        # Platform admin merged tool
        "admin_platform_tool": "admin_endpoints_tool",
        
        # Instance tools
        "instance_tool": "instance_endpoints_tool",
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

def clear_cache():
    """
    Clear all cached configuration data.
    
    Call this if configuration files change during runtime.
    """
    load_toolset_apis.cache_clear()
    load_tool_grouping.cache_clear()
    load_manual_confirmation_rules.cache_clear()
    logger.info("Configuration cache cleared")


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
        
        # Check for unknown tools
        grouping = load_tool_grouping()
        for api in apis:
            tool = get_tool_for_api(api["path"])
            if tool == "unknown_tool":
                errors.append(f"API path '{api['path']}' doesn't match any known tool pattern")
                
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
    
    # Validate tool grouping
    try:
        grouping = load_tool_grouping()
        if not grouping:
            results["tool_grouping.txt"] = ["No tool groupings defined"]
    except Exception as e:
        results["tool_grouping.txt"] = [str(e)]
    
    # Validate confirmation rules
    try:
        rules = load_manual_confirmation_rules()
        if not rules:
            results["manual_confirmation.txt"] = ["No confirmation rules defined"]
    except Exception as e:
        results["manual_confirmation.txt"] = [str(e)]
    
    return results
