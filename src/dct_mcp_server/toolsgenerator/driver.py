#!/usr/bin/env python3

"""
Driver code for the MCP server tool generation from Delphix DCT OpenAPI specification.

This script downloads the OpenAPI YAML specification from the DCT server,
parses it, and generates tool files for each API category. API definitions
are sourced from config/toolsets/*.txt files with inline tool grouping via # TOOL headers.

Generated tool files are saved in the dct_mcp_server/tools directory.
Each generated function includes:
- Function signature with parameters and types.
- Docstrings with parameter descriptions.
- Implementation using utility functions for making API requests.

Configuration Files Used:
- config/toolsets/*.txt: Toolset definitions with METHOD|path|action format and # TOOL headers
"""


import yaml
import os
import glob
import re
import requests
import urllib3
import logging
import tempfile
from dct_mcp_server.config.config import get_dct_config
from dct_mcp_server.config.loader import TOOLSETS_DIR

# Get the absolute path of the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# For uvx/package installations, use the package directory structure
if 'site-packages' in __file__:
    # Use temp directory for generated tools to avoid permission issues
    TOOLS_DIR = os.path.join(tempfile.gettempdir(), "dct_mcp_tools")
else:
    # For local development, use the project structure
    TOOLS_DIR = os.path.join(project_root, "src/dct_mcp_server/tools/")

INDENT_SIZE = 4

logger = logging.getLogger(__name__)

# Global structure to hold tools grouped by tool name
# Format: {"vdb_tool": [{"method": "POST", "path": "/vdbs/search", "action": "search"}, ...]}
TOOLS_BY_NAME = {}

# Domain terminology hints injected into tool docstrings so the AI agent
# correctly interprets Delphix-specific jargon used as verbs in user prompts.
TOOL_DOMAIN_HINTS = {
    "data_tool": (
        "IMPORTANT — Delphix domain terminology:\n"
        "  • \"dSource\" is often used as a VERB meaning \"create/link a dSource\" "
        "(i.e. ingest a source database). When a user says "
        "\"dSource database X\", they want to LINK a new dSource for database X, "
        "NOT look up an existing dSource named X. Use the appropriate "
        "dsource_link_* action (dsource_link_oracle, dsource_link_mssql, "
        "dsource_link_ase, dsource_link_appdata) depending on the database type.\n"
        "  • \"provision\" or \"spin up\" a VDB or \"create a golden image of a "
        "VDB\" means creating a virtual database from a dSource or bookmark  —"
        " use provision_by_timestamp, provision_by_snapshot, etc.\n"
        "  • \"refresh\" a VDB means updating it with newer data from its parent — "
        "use refresh_vdb_by_timestamp, refresh_vdb_by_snapshot, etc."
    ),
}

# Actions whose request payload depends on a toolkit schema (AppData link/provision).
# When generating docstrings for these actions, we append a hint telling the AI to
# call toolkit_tool(action='search') to find the right toolkit before filling params.
# Maps action name -> hint group.
# "dsource" group: payload field is 'parameters' (and 'sync_parameters').
# "provision" group: payload fields are 'appdata_source_params' and 'appdata_config_params'.
ACTIONS_REQUIRING_TOOLKIT_SCHEMA: dict[str, str] = {
    "dsource_link_appdata": "dsource",
    "dsource_link_appdata_defaults": "dsource",
    "update_appdata_dsource": "dsource",
    "provision_by_timestamp": "provision",
    "provision_by_snapshot": "provision",
    "provision_from_bookmark": "provision",
    "provision_by_location": "provision",
    "provision_empty_vdb": "provision",
}

_TOOLKIT_SCHEMA_HINT_COMMON = (
    "IMPORTANT — AppData toolkit schema: "
    "Before populating toolkit-specific parameters, call toolkit_tool(action='search') "
    "to list available toolkits. Filter results by the engine_id of the environment you "
    "are operating on — use only toolkits whose engine_id matches.\n"
)

TOOLKIT_SCHEMA_HINT_DSOURCE = (
    _TOOLKIT_SCHEMA_HINT_COMMON
    + "    Use the matching toolkit's 'linked_source_definition.parameters' schema "
    "to populate 'parameters', and 'snapshot_parameters_definition' for 'sync_parameters'."
)

TOOLKIT_SCHEMA_HINT_PROVISION = (
    "IMPORTANT — AppData VDB only: "
    "If provisioning an AppData VDB (i.e., you need to populate 'appdata_source_params' "
    "or 'appdata_config_params'), call toolkit_tool(action='search') first and filter "
    "by the engine_id of the target environment, and use environment_user_id. "
    "Use the matching toolkit's 'virtual_source_definition.parameters' schema for "
    "'appdata_source_params', and 'source_config_definition.parameters' for 'appdata_config_params'. "
    "For Oracle, MSSQL, PostgreSQL, or other non-AppData types, skip this step."
)


def load_api_endpoints_from_toolsets():
    """
    Load API endpoints from the SELECTED toolset file and group by TOOL NAME.
    
    Only reads the toolset specified by DCT_TOOLSET config (default: self_service).
    Parses tool comments like "# TOOL 1: vdb_tool" to group APIs into unified tools.
    Each tool will support multiple actions (search, get, create, etc.).
    """
    global TOOLS_BY_NAME
    TOOLS_BY_NAME = {}
    
    if not TOOLSETS_DIR.exists():
        logger.error(f"Toolsets directory not found: {TOOLSETS_DIR}")
        return
    
    # Get the selected toolset from config
    dct_config = get_dct_config()
    selected_toolset = dct_config.get("toolset", "self_service")
    
    # Handle "auto" mode - use self_service as default
    if selected_toolset == "auto":
        selected_toolset = "self_service"
    
    toolset_file = TOOLSETS_DIR / f"{selected_toolset}.txt"
    
    if not toolset_file.exists():
        logger.error(f"Toolset file not found: {toolset_file}")
        return
    
    logger.info(f"Loading toolset: {selected_toolset} from {toolset_file}")
    
    # Parse the selected toolset file
    _parse_toolset_file(toolset_file)
    
    # Log summary
    total_apis = sum(len(apis) for apis in TOOLS_BY_NAME.values())
    logger.info(f"Loaded {total_apis} APIs grouped into {len(TOOLS_BY_NAME)} unified tools")
    for tool_name, apis in TOOLS_BY_NAME.items():
        logger.info(f"  {tool_name}: {len(apis)} actions")


def _parse_toolset_file(toolset_file):
    """
    Parse a single toolset file and populate TOOLS_BY_NAME.
    
    Handles inheritance directives (@inherit:parent_toolset).
    """
    global TOOLS_BY_NAME
    current_tool = None
    
    with open(toolset_file, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Handle inheritance directive
            if line.startswith('@inherit:'):
                parent_name = line.split(':')[1].strip()
                parent_file = TOOLSETS_DIR / f"{parent_name}.txt"
                if parent_file.exists():
                    logger.info(f"  Inheriting from: {parent_name}")
                    _parse_toolset_file(parent_file)
                else:
                    logger.warning(f"Parent toolset not found: {parent_name}")
                continue
            
            # Check for tool header comments like "# TOOL 1: vdb_tool"
            # Must start with "# TOOL" followed by number and colon (not "# Inherited: TOOL")
            tool_header_match = re.match(r'^#\s*TOOL\s+\d+\s*:\s*(\w+)', line, re.IGNORECASE)
            if tool_header_match:
                # Extract tool name from regex group
                current_tool = tool_header_match.group(1).strip()
                if current_tool and current_tool not in TOOLS_BY_NAME:
                    TOOLS_BY_NAME[current_tool] = []
                continue
            
            # Skip other comments
            if line.startswith('#'):
                continue
            
            # Parse METHOD|path|action format
            parts = line.split('|')
            if len(parts) >= 3 and current_tool:
                http_method = parts[0].strip().upper()
                api_path = parts[1].strip()
                action_name = parts[2].strip()
                
                api_entry = {
                    "method": http_method,
                    "path": api_path,
                    "action": action_name
                }
                
                # Avoid duplicates
                if api_entry not in TOOLS_BY_NAME[current_tool]:
                    TOOLS_BY_NAME[current_tool].append(api_entry)


# Keep old function for backwards compatibility
def load_api_endpoints():
    """Legacy function - now delegates to load_api_endpoints_from_toolsets."""
    load_api_endpoints_from_toolsets()


def download_open_api_yaml(api_url: str, save_path: str):
    """Downloads the OpenAPI YAML from the given URL."""
    try:
        logger.info(f"Downloading OpenAPI spec from {api_url}...")
        
        # Get DCT configuration for proper authentication and SSL settings
        dct_config = get_dct_config()
        verify_ssl = dct_config.get("verify_ssl", False)
        api_key = dct_config.get("api_key")
        
        # Prepare headers with authentication if API key is available
        headers = {
            "Accept": "application/x-yaml, text/yaml, application/json",
            "User-Agent": "dct-mcp-server-toolgen/1.0"
        }
        if api_key:
            headers["Authorization"] = f"apk {api_key}"

        # Use the configured SSL verification and authentication
        response = requests.get(api_url, timeout=30, verify=verify_ssl, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        logger.info(f"Successfully saved OpenAPI spec to {save_path}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error downloading OpenAPI spec: {e}")
        raise

translated_dict_for_types = {
    "integer": "int",
    "string": "str",
    "boolean": "bool",
    "float": "float",
}

prefix = """from mcp.server.fastmcp import FastMCP
from typing import Dict,Any,Optional
from dct_mcp_server.core.decorators import log_tool_execution
from dct_mcp_server.config import get_confirmation_for_operation, requires_confirmation
import asyncio
import logging

client = None
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIRMATION INTEGRATION
# =============================================================================
# For destructive operations (DELETE, POST .../delete), generated tools should:
# 1. Call requires_confirmation(method, path) to check if confirmation needed
# 2. If True, include confirmation_message in the response
# 3. LLM should use check_operation_confirmation meta-tool before executing
#
# Example usage in generated tool:
#   confirmation = get_confirmation_for_operation("DELETE", "/vdbs/{id}")
#   if confirmation["level"] != "none":
#       return {
#           "requires_confirmation": True,
#           "confirmation_level": confirmation["level"],
#           "confirmation_message": confirmation["message"],
#           "operation": "delete_vdb"
#       }
# =============================================================================

def check_confirmation(method: str, api_path: str, action: str, tool_name: str, confirmed: bool = False, request_params: Optional[Dict[str, Any]] = None, request_body: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    \"\"\"Check if operation requires confirmation. Returns confirmation response or None if confirmed/not needed.\"\"\"
    confirmation = get_confirmation_for_operation(method, api_path)
    if confirmation["level"] != "none" and not confirmed:
        # Merge query params and body into a single review dict so the LLM can
        # render the exact payload that will be sent. None values are already
        # stripped upstream by build_params / body filter.
        review: Dict[str, Any] = {}
        if request_params:
            review.update(request_params)
        if request_body:
            review.update(request_body)
        is_review_critical = action.startswith("provision_") or action.startswith("dsource_link_") or action == "dsource_create_snapshot"
        instructions = (
            "STOP: You MUST display the confirmation_message to the user and wait for their EXPLICIT "
            "approval before re-calling with confirmed=True. Do NOT proceed without user consent."
        )
        if is_review_critical:
            instructions = (
                "STOP — REVIEW AND SUBMIT: Before asking the user to confirm, render 'review_parameters' "
                "as a Markdown table with columns | Parameter | Value | (one row per key). Then show the "
                "'confirmation_message' and the endpoint (method + api_path). Wait for EXPLICIT user approval, "
                "then re-call with confirmed=True and the SAME parameters. Do NOT proceed without consent."
            )
        return {
            "status": "confirmation_required",
            "confirmation_level": confirmation["level"],
            "confirmation_message": confirmation.get("message", "Please confirm this operation."),
            "action": action,
            "tool": tool_name,
            "api_path": api_path,
            "method": method,
            "review_parameters": review,
            "instructions": instructions,
        }
    return None

async def make_api_request(method: str, endpoint: str, params: dict = None, json_body: dict = None):
    \"\"\"Utility function to make API requests with consistent parameter handling.\"\"\"
    return await client.make_request(method, endpoint, params=params or {}, json=json_body)

def build_params(**kwargs):
    \"\"\"Build parameters dictionary excluding None and empty string values.\"\"\"
    return {k: v for k, v in kwargs.items() if v is not None and v != ''}

"""

def create_register_tool_function(tool_name, apis):
    func_str = "\n"
    func_str += "def register_tools(app, dct_client):\n"
    func_str += " "* INDENT_SIZE + "global client\n"
    func_str += " "* INDENT_SIZE + "client = dct_client\n"
    func_str += " "* INDENT_SIZE + f"logger.info(f'Registering tools for {tool_name}...')\n"
    func_str += " "* INDENT_SIZE + "try:\n"
    for function in apis:
        func_str += " "* INDENT_SIZE*2 + f"logger.info(f'  Registering tool function: {function}')\n"
        func_str += " "* INDENT_SIZE*2 + f"app.add_tool({function}, name=\"{function}\")\n"
    func_str += " "* INDENT_SIZE + "except Exception as e:\n"
    func_str += " "* INDENT_SIZE*2 + f"logger.error(f'Error registering tools for {tool_name}: {{e}}')\n"
    func_str += " "* INDENT_SIZE + f"logger.info(f'Tools registration finished for {tool_name}.')\n"
    return func_str

def read_open_api_yaml(api_file):
    yaml_body = ""
    with open(api_file, "r") as f:
        yaml_body = yaml.safe_load(f)
    return yaml_body


def resolve_ref(ref: str, root: dict):
    """
    Resolve a JSON pointer $ref like '#/components/schemas/DSource'
    inside a loaded OpenAPI YAML dict.
    """
    if not ref.startswith('#/'):
        raise ValueError(f"Unsupported ref format: {ref}")

    # Remove starting '#/' and split by "/"
    path = ref.lstrip('#/').split('/')

    node = root
    for part in path:
        node = node[part]
    return node


def resolve_schema_properties(schema: dict, api_spec: dict) -> tuple:
    """
    Resolve schema properties, handling $ref and allOf composition.

    Returns:
        tuple: (properties dict, required list, key_properties set)
               key_properties contains property names from action-specific
               sub-schemas (inline objects and small $ref'd schemas), as
               opposed to large inherited base schemas.
    """
    # Resolve top-level $ref if present
    if "$ref" in schema:
        schema = resolve_ref(schema["$ref"], api_spec)

    # Handle allOf composition
    if "allOf" in schema:
        combined_properties = {}
        combined_required = []
        key_properties = set()

        for sub_schema in schema["allOf"]:
            is_ref = "$ref" in sub_schema
            ref_name = sub_schema.get("$ref", "").split("/")[-1] if is_ref else ""

            # Resolve $ref in sub-schema
            if is_ref:
                sub_schema = resolve_ref(sub_schema["$ref"], api_spec)

            # Recursively handle nested allOf
            if "allOf" in sub_schema:
                nested_props, nested_required, nested_key = resolve_schema_properties(sub_schema, api_spec)
                combined_properties.update(nested_props)
                combined_required.extend(nested_required)
                # Don't propagate key_properties from base schemas
            else:
                props = sub_schema.get("properties", {})
                combined_properties.update(props)
                combined_required.extend(sub_schema.get("required", []))

                # Determine if this sub-schema is action-specific or a large base.
                # Inline objects (not $ref) and small $ref'd schemas (<=5 props)
                # are considered action-specific — their properties are "key".
                # Large $ref'd schemas (e.g. BaseProvisionVDBParameters with 60+
                # props via nested allOf) are inherited base schemas.
                if not is_ref or len(props) <= 5:
                    key_properties.update(props.keys())

        return combined_properties, combined_required, key_properties

    # Direct properties (no allOf) — all are key
    props = schema.get("properties", {})
    return props, schema.get("required", []), set(props.keys())


def generate_tools_from_openapi():
    """
    Generates UNIFIED tool files from OpenAPI spec based on TOOLS_BY_NAME.
    
    Each tool supports multiple actions through an 'action' parameter.
    Example: vdb_tool(action="search", ...) or vdb_tool(action="start", vdb_id="...")
    """
    load_api_endpoints_from_toolsets()

    # Get DCT base URL from config
    dct_config = get_dct_config()
    base_url = dct_config.get("base_url")
    if not base_url:
        logger.error("DCT_BASE_URL not configured. Cannot download OpenAPI specification.")
        raise ValueError("DCT_BASE_URL is required for tool generation")
    
    # Construct the OpenAPI spec URL
    client_address = f"{base_url.rstrip('/')}/dct/static/api-external.yaml"
    logger.info(f"OpenAPI spec URL: {client_address}")
    
    # Use temp directory for package installations, project directory for local development
    if 'site-packages' in __file__:
        API_FILE = os.path.join(tempfile.gettempdir(), "api.yaml")
    else:
        API_FILE = os.path.join(project_root, "src", "api.yaml")
    
    download_open_api_yaml(client_address, API_FILE)

    api_spec = read_open_api_yaml(API_FILE)
    logger.info(f"Unified tools to generate: {list(TOOLS_BY_NAME.keys())}")
    
    os.makedirs(TOOLS_DIR, exist_ok=True)

    # Clean up existing generated tool files before creating new ones
    existing_tools = glob.glob(os.path.join(TOOLS_DIR, "*_tool.py"))
    for tool_file in existing_tools:
        try:
            os.remove(tool_file)
            logger.info(f"Deleted existing tool file: {tool_file}")
        except OSError as e:
            logger.warning(f"Could not delete {tool_file}: {e}")
    
    logger.info(f"Cleaned up {len(existing_tools)} existing tool files")

    # Group tools by module for file organization
    module_tools = {}
    for tool_name, apis in TOOLS_BY_NAME.items():
        # Determine module based on first API path
        if apis:
            first_path = apis[0]["path"]
            module_name = _get_module_for_path(first_path)
        else:
            module_name = "misc_endpoints"
        
        if module_name not in module_tools:
            module_tools[module_name] = {}
        module_tools[module_name][tool_name] = apis

    # Generate one file per module containing unified tools
    for module_name, tools in module_tools.items():
        TOOL_FILE = os.path.join(TOOLS_DIR, f"{module_name}_tool.py")
        
        tool_file_content = prefix

        function_lists = []

        for tool_name, apis in tools.items():
            tool_code = _generate_unified_tool(tool_name, apis, api_spec)
            if tool_code:  # Only add if tool was successfully generated
                tool_file_content += tool_code
                function_lists.append(tool_name)

        # Skip generating file if no tools were successfully generated
        if not function_lists:
            logger.warning(f"Skipping module {module_name} - no valid tools generated")
            continue

        tool_file_content += create_register_tool_function(module_name, function_lists)

        with open(TOOL_FILE, "w") as f:
            f.write(tool_file_content)
        
        logger.info(f"Generated {TOOL_FILE} with {len(function_lists)} unified tools")

    # Delete the api.yaml file after generating all tools
    if os.path.exists(API_FILE):
        os.remove(API_FILE)


def _get_module_for_path(api_path: str) -> str:
    """Determine module name based on API path."""
    path_to_module = {
        # Dataset endpoints
        "/vdbs": "dataset_endpoints",
        "/vdb-groups": "dataset_endpoints",
        "/dsources": "dataset_endpoints",
        "/snapshots": "dataset_endpoints",
        "/bookmarks": "dataset_endpoints",
        "/sources": "dataset_endpoints",
        "/data-connections": "dataset_endpoints",
        "/timeflows": "dataset_endpoints",
        
        # Job endpoints
        "/jobs": "job_endpoints",
        
        # Environment endpoints
        "/environments": "environment_endpoints",
        "/toolkits": "environment_endpoints",
        
        # Engine endpoints
        "/management/engines": "engine_endpoints",
        "/engines": "engine_endpoints",
        
        # Compliance endpoints
        "/masking": "compliance_endpoints",
        "/connectors": "compliance_endpoints",
        "/executions": "compliance_endpoints",
        "/algorithms": "compliance_endpoints",
        
        # Reports endpoints
        "/reporting": "reports_endpoints",
        "/reports": "reports_endpoints",
        
        # IAM endpoints (accounts, roles, access-groups, api-clients)
        "/management/accounts": "iam_endpoints",
        "/roles": "iam_endpoints",
        "/access-groups": "iam_endpoints",
        "/management/api-clients": "iam_endpoints",
        "/management/tags": "iam_endpoints",
        
        # Policy endpoints (replication, virtualization policies)
        "/replication-profiles": "policy_endpoints",
        "/virtualization-policies": "policy_endpoints",
        
        # Admin/Platform endpoints (AI, telemetry, SMTP, LDAP, SAML, proxy, license, properties)
        "/ai": "admin_endpoints",
        "/management/properties": "admin_endpoints",
        "/management/telemetry": "admin_endpoints",
        "/management/smtp": "admin_endpoints",
        "/management/ldap-config": "admin_endpoints",
        "/management/saml-config": "admin_endpoints",
        "/management/proxy-configuration": "admin_endpoints",
        "/management/license": "admin_endpoints",
        
        # Template endpoints
        "/database-templates": "template_endpoints",
        "/hook-templates": "template_endpoints",
    }
    
    # Check from most specific to least specific (longer paths first)
    for prefix in sorted(path_to_module.keys(), key=len, reverse=True):
        if api_path.startswith(prefix):
            return path_to_module[prefix]
    return "misc_endpoints"



def _generate_unified_tool(tool_name: str, apis: list, api_spec: dict) -> str:
    """
    Generate a unified tool function that supports multiple actions.
    
    Args:
        tool_name: Name of the tool (e.g., "vdb_tool")
        apis: List of API entries [{"method": "POST", "path": "/vdbs/search", "action": "search"}, ...]
        api_spec: Parsed OpenAPI specification
    
    Returns:
        Generated Python code for the unified tool function
    """
    # Collect all parameters across all actions
    all_params = {}  # {param_name: {"type": str, "required_for": [actions], "description": str, "param_type": str}}
    action_details = {}  # {action_name: {"method": str, "path": str, "path_params": [], "has_filter": bool, "body_params": []}}
    
    # Extract resource type from tool name for descriptions
    resource_type = tool_name.replace("_tool", "").replace("_", " ").upper()
    
    for api_entry in apis:
        action = api_entry["action"]
        method = api_entry["method"]
        path = api_entry["path"]
        
        path_item = api_spec.get("paths", {}).get(path, {})
        operation = path_item.get(method.lower())
        
        if not operation:
            logger.warning(f"No operation found for {method} {path}")
            continue
        
        # Extract path parameters
        path_params = re.findall(r'\{(\w+)\}', path)
        path_params_snake = [(p, re.sub(r'(?<!^)(?=[A-Z])', '_', p).lower()) for p in path_params]
        
        has_filter = operation.get('x-filterable', False)
        
        action_details[action] = {
            "method": method,
            "path": path,
            "path_params": path_params_snake,
            "has_filter": has_filter,
            "summary": operation.get("summary", ""),
            "operation_id": operation.get("operationId", action)
        }
        
        # Add path parameters
        for orig_name, snake_name in path_params_snake:
            param_key = snake_name
            if param_key not in all_params:
                # Find description from parameters
                desc = f"The unique identifier for the {orig_name.replace('Id', '')}."
                for param in operation.get("parameters", []):
                    param_def = resolve_ref(param["$ref"], api_spec) if "$ref" in param else param
                    if param_def.get("name") == orig_name:
                        desc = param_def.get("description", desc)
                        break
                all_params[param_key] = {"type": "str", "required_for": [], "description": desc, "param_type": "path"}
            all_params[param_key]["required_for"].append(action)
        
        # Add query parameters
        for param in operation.get("parameters", []):
            param_def = resolve_ref(param["$ref"], api_spec) if "$ref" in param else param
            if param_def.get("in") == "path":
                continue

            name = param_def.get("name", "unknown")
            try:
                param_type = translated_dict_for_types.get(param_def['schema']['type'], "str")
                desc = param_def.get("description", "Query parameter")

                # Include enum values in description if they exist
                enum_values = param_def.get('schema', {}).get('enum')
                if enum_values:
                    desc = f"{desc} Valid values: {', '.join(str(v) for v in enum_values)}."

                # Capture default value from the spec if present
                default_value = param_def.get('schema', {}).get('default')
                if default_value is not None:
                    desc = f"{desc} (Default: {default_value})"

                if name not in all_params:
                    all_params[name] = {"type": param_type, "required_for": [], "description": desc, "param_type": "query", "default": default_value}
                elif default_value is not None and all_params[name].get("default") is None:
                    all_params[name]["default"] = default_value
                    all_params[name]["description"] = desc
                all_params[name]["required_for"].append(action)
            except KeyError:
                continue
        
        # Add request body parameters for POST/PUT/PATCH
        body_params_for_action = []  # Initialize for all methods
        request_body = operation.get("requestBody", {})
        
        # Resolve $ref in requestBody if present
        if "$ref" in request_body:
            request_body = resolve_ref(request_body["$ref"], api_spec)
        
        if request_body and method.upper() in ["POST", "PUT", "PATCH"]:
            content = request_body.get("content", {})
            json_content = content.get("application/json", {})
            schema = json_content.get("schema", {})
            
            # Use helper to resolve schema properties (handles $ref and allOf)
            properties, required_props, key_props = resolve_schema_properties(schema, api_spec)
            
            for prop_name, prop_def in properties.items():
                # Handle nested $ref in property definition
                if "$ref" in prop_def:
                    prop_def = resolve_ref(prop_def["$ref"], api_spec)

                prop_type = prop_def.get("type", "string")
                is_json_param = prop_type in ("object", "array")

                if prop_type in translated_dict_for_types or is_json_param:
                    if is_json_param:
                        python_type = "dict" if prop_type == "object" else "list"
                    else:
                        python_type = translated_dict_for_types[prop_type]
                    desc = prop_def.get("description", "Request body parameter")

                    # Include enum values in description if they exist
                    enum_values = prop_def.get('enum')
                    if enum_values:
                        desc = f"{desc} Valid values: {', '.join(str(v) for v in enum_values)}."

                    # Add JSON hint for object/array params
                    if is_json_param:
                        json_kind = "JSON object" if prop_type == "object" else "JSON array"
                        desc = f"{desc} (Pass as {json_kind})"

                    # Read x-dct-toolkit-subcommand to tag database-type-specific params
                    toolkit_subcommand = prop_def.get("x-dct-toolkit-subcommand")
                    if toolkit_subcommand:
                        subcommand_labels = {
                            "oracle": "Oracle only",
                            "mssql": "MSSql only",
                            "sybase": "ASE/Sybase only",
                            "appdata": "AppData only",
                            "postgres": "Postgres only",
                        }
                        label = subcommand_labels.get(toolkit_subcommand, f"{toolkit_subcommand} only")
                        desc = f"[{label}] {desc}"

                    # Convert camelCase to snake_case for consistency
                    snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', prop_name).lower()
                    body_params_for_action.append((prop_name, snake_name, is_json_param))

                    # Capture default value from the spec if present
                    default_value = prop_def.get("default")
                    if default_value is not None:
                        desc = f"{desc} (Default: {default_value})"

                    if snake_name not in all_params:
                        all_params[snake_name] = {"type": python_type, "required_for": [], "key_for": [], "description": desc, "param_type": "body", "is_json": is_json_param, "default": default_value, "toolkit_subcommand": toolkit_subcommand}
                    elif default_value is not None and all_params[snake_name].get("default") is None:
                        # Update default if this action provides one and we didn't have one yet
                        all_params[snake_name]["default"] = default_value
                        all_params[snake_name]["description"] = desc
                    if prop_name in required_props:
                        all_params[snake_name]["required_for"].append(action)
                    elif prop_name in key_props:
                        # Key parameter: action-specific but not in the required list.
                        # Surface these so the LLM knows they are the primary inputs.
                        all_params[snake_name].setdefault("key_for", []).append(action)
        
        # Store body params for this action
        action_details[action]["body_params"] = body_params_for_action
        
        # Add filter_expression for search actions
        if has_filter:
            if "filter_expression" not in all_params:
                all_params["filter_expression"] = {
                    "type": "str",
                    "required_for": [],
                    "description": "Filter expression to narrow results (e.g., \"name CONTAINS 'prod'\")",
                    "param_type": "body"
                }
    
    # Skip generating tool if no valid actions were found
    if not action_details:
        logger.warning(f"Skipping tool '{tool_name}' - no valid API operations found")
        return ""
    
    # Build function signature
    actions_list = list(action_details.keys())
    actions_literal = "|".join([f"'{a}'" for a in actions_list])
    
    func_code = f"@log_tool_execution\nasync def {tool_name}(\n"
    func_code += f"    action: str,  # One of: {', '.join(actions_list)}\n"

    # Add all parameters as optional (since they depend on action)
    for param_name, param_info in sorted(all_params.items()):
        default_value = param_info.get("default")
        # Database-type-specific params (e.g. recovery_model for MSSQL) must
        # default to None so they are never sent for unrelated database types.
        if param_info.get("toolkit_subcommand"):
            default_value = None
        # Body params must default to None in the signature — baking the spec
        # default in would send the field for every call, even when the caller
        # omits it, which breaks DB-type-gated fields like
        # availability_group_backup_policy (MSSql-only). The spec default is
        # still surfaced in the docstring description.
        if param_info.get("param_type") == "body":
            default_value = None
        if default_value is not None:
            # Use the spec default in the signature so the tool behaves correctly even if the LLM omits it
            if isinstance(default_value, bool):
                default_repr = repr(default_value)
            elif isinstance(default_value, str):
                default_repr = repr(default_value)
            else:
                default_repr = repr(default_value)
            func_code += f"    {param_name}: Optional[{param_info['type']}] = {default_repr},\n"
        else:
            func_code += f"    {param_name}: Optional[{param_info['type']}] = None,\n"

    # Add confirmed parameter for destructive operation confirmation
    func_code += f"    confirmed: Optional[bool] = None,\n"

    func_code += ") -> Dict[str, Any]:\n"
    
    # Build comprehensive docstring with detailed action documentation
    docstring_lines = []
    docstring_lines.append(f"Unified tool for {resource_type} operations.")
    docstring_lines.append("")
    docstring_lines.append(f"This tool supports {len(actions_list)} actions: {', '.join(actions_list)}")
    docstring_lines.append("")

    # Inject domain terminology hints for tools that need them
    if tool_name in TOOL_DOMAIN_HINTS:
        docstring_lines.append(TOOL_DOMAIN_HINTS[tool_name])
        docstring_lines.append("")

    # =========================================================================
    # DETAILED ACTION DOCUMENTATION
    # =========================================================================
    docstring_lines.append("=" * 70)
    docstring_lines.append("ACTION REFERENCE")
    docstring_lines.append("=" * 70)
    
    for action_name, details in action_details.items():
        docstring_lines.append("")
        docstring_lines.append(f"ACTION: {action_name}")
        docstring_lines.append("-" * 40)
        docstring_lines.append(f"Summary: {details['summary']}")
        docstring_lines.append(f"Method: {details['method']}")
        docstring_lines.append(f"Endpoint: {details['path']}")
        
        # Required parameters for this action
        required_params = [p for p, info in all_params.items() if action_name in info["required_for"]]
        if required_params:
            docstring_lines.append(f"Required Parameters: {', '.join(required_params)}")

        # Key parameters: action-specific but not strictly required (e.g. provide at least one of these)
        key_params = [p for p, info in all_params.items()
                      if action_name in info.get("key_for", []) and p not in required_params]
        if key_params:
            docstring_lines.append(f"Key Parameters (provide as applicable): {', '.join(key_params)}")
        
        # Get full operation details from api_spec for filterable fields
        path_item = api_spec.get("paths", {}).get(details["path"], {})
        operation = path_item.get(details["method"].lower(), {})
        
        # Document filterable fields for search actions
        if details["has_filter"]:
            docstring_lines.append("")
            docstring_lines.append("Filterable Fields:")
            try:
                responses = operation.get("responses", {})
                for status_code, resp_details in responses.items():
                    if 'content' in resp_details and 'application/json' in resp_details['content']:
                        schema = resp_details['content']['application/json'].get('schema', {})
                        if 'properties' in schema and 'items' in schema['properties']:
                            items_schema = schema['properties']['items']
                            if 'items' in items_schema and '$ref' in items_schema['items']:
                                response_schema = resolve_ref(items_schema['items']['$ref'], api_spec)
                                props = response_schema.get("properties", {})
                                for prop_name, prop_def in props.items():
                                    prop_desc = prop_def.get("description", "")
                                    if len(prop_desc) > 60:
                                        prop_desc = prop_desc[:57] + "..."
                                    docstring_lines.append(f"    - {prop_name}: {prop_desc}")
                                break
            except Exception:
                docstring_lines.append("    (See API documentation for filterable fields)")
            
            docstring_lines.append("")
            docstring_lines.append("Filter Syntax:")
            docstring_lines.append("    Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN")
            docstring_lines.append("    Combine: AND, OR")
            docstring_lines.append("    Example: \"name CONTAINS 'prod' AND status EQ 'RUNNING'\"")
        
        # Example for this action (include both required and key params)
        docstring_lines.append("")
        docstring_lines.append("Example:")
        example_params = [f"action='{action_name}'"]
        for param, info in all_params.items():
            if action_name in info["required_for"] or action_name in info.get("key_for", []):
                if param.endswith("_id"):
                    example_params.append(f"{param}='example-{param.replace('_id', '')}-123'")
                elif param == "filter_expression":
                    example_params.append(f"filter_expression=\"name CONTAINS 'test'\"")
                else:
                    example_params.append(f"{param}=...")
        docstring_lines.append(f"    >>> {tool_name}({', '.join(example_params)})")

        # Inject toolkit-schema resource hint for AppData-related actions
        hint_group = ACTIONS_REQUIRING_TOOLKIT_SCHEMA.get(action_name)
        if hint_group == "dsource":
            docstring_lines.append("")
            docstring_lines.append(f"    {TOOLKIT_SCHEMA_HINT_DSOURCE}")
        elif hint_group == "provision":
            docstring_lines.append("")
            docstring_lines.append(f"    {TOOLKIT_SCHEMA_HINT_PROVISION}")

    # =========================================================================
    # PARAMETERS SECTION (grouped by database type)
    # =========================================================================
    docstring_lines.append("")
    docstring_lines.append("=" * 70)
    docstring_lines.append("PARAMETERS")
    docstring_lines.append("=" * 70)
    docstring_lines.append("")
    docstring_lines.append("Args:")
    docstring_lines.append(f"    action (str): The operation to perform. One of: {', '.join(actions_list)}")

    # Separate params into general vs database-type-specific groups
    general_params = {}
    typed_params = {}  # {subcommand: {param_name: param_info}}
    for param_name, param_info in sorted(all_params.items()):
        subcommand = param_info.get("toolkit_subcommand")
        if subcommand:
            typed_params.setdefault(subcommand, {})[param_name] = param_info
        else:
            general_params[param_name] = param_info

    def _format_param_line(param_name, param_info):
        required_actions = param_info["required_for"]
        if required_actions:
            req_note = f"Required for: {', '.join(required_actions)}"
        else:
            req_note = "Optional for all actions"
        desc = param_info['description']
        if len(desc) > 80:
            desc = desc[:77] + "..."
        return [
            f"    {param_name} ({param_info['type']}): {desc}",
            f"        [{req_note}]",
        ]

    # General parameters (applicable to all database types)
    docstring_lines.append("")
    docstring_lines.append("  -- General parameters (all database types) --")
    for param_name, param_info in general_params.items():
        docstring_lines.extend(_format_param_line(param_name, param_info))

    # Database-type-specific parameter groups
    subcommand_group_labels = {
        "oracle": "Oracle-specific parameters",
        "mssql": "MSSql-specific parameters",
        "sybase": "ASE/Sybase-specific parameters",
        "appdata": "AppData-specific parameters",
        "postgres": "Postgres-specific parameters",
    }
    for subcommand, params in sorted(typed_params.items()):
        group_label = subcommand_group_labels.get(subcommand, f"{subcommand}-specific parameters")
        docstring_lines.append("")
        docstring_lines.append(f"  -- {group_label} (SKIP if not provisioning {subcommand}) --")
        for param_name, param_info in params.items():
            docstring_lines.extend(_format_param_line(param_name, param_info))
    
    docstring_lines.append("")
    docstring_lines.append("Returns:")
    docstring_lines.append("    Dict[str, Any]: The API response containing operation results")
    docstring_lines.append("")
    docstring_lines.append("Raises:")
    docstring_lines.append("    Returns error dict if required parameters are missing for the action")
    
    docstring = '    """\n'
    for line in docstring_lines:
        docstring += f"    {line}\n"
    docstring += '    """\n'
    
    func_code += docstring
    
    # Build function body with action routing
    func_code += "    # Route to appropriate API based on action\n"
    
    first = True
    for action_name, details in action_details.items():
        if first:
            func_code += f"    if action == '{action_name}':\n"
            first = False
        else:
            func_code += f"    elif action == '{action_name}':\n"
        
        # Build endpoint with path parameters
        path = details["path"]
        path_params = details["path_params"]
        
        if path_params:
            # Check required parameters
            for orig, snake in path_params:
                func_code += f"        if {snake} is None:\n"
                func_code += f"            return {{'error': 'Missing required parameter: {snake} for action {action_name}'}}\n"
            
            endpoint_expr = f"f'{path}'"
            for orig, snake in path_params:
                endpoint_expr = endpoint_expr.replace("{" + orig + "}", "{" + snake + "}")
            func_code += f"        endpoint = {endpoint_expr}\n"
            endpoint_var = "endpoint"
        else:
            endpoint_var = f"'{path}'"
        
        # Build params dict
        func_code += "        params = build_params("
        # Add query params that are relevant to this action
        query_params = [p for p, info in all_params.items()
                       if action_name in info["required_for"]
                       and not p.endswith("_id")
                       and p != "filter_expression"]
        if query_params:
            func_code += ", ".join([f"{p}={p}" for p in query_params])
        func_code += ")\n"

        # Build request body BEFORE confirmation check so the review payload
        # can surface the exact values that will be sent to DCT.
        method = details["method"]
        body_var = "None"
        if details["has_filter"] and method == "POST":
            func_code += "        body = {'filter_expression': filter_expression} if filter_expression else {}\n"
            body_var = "body"
        elif method in ["POST", "PUT", "PATCH"]:
            body_params = details.get("body_params", [])
            if body_params:
                body_items = ", ".join([
                    f"'{orig}': {snake}"
                    for orig, snake, is_json in body_params
                ])
                body_param_names = {snake for _, snake, _ in body_params}
                if "environment_user_id" in body_param_names:
                    func_code += "        if not environment_user_id:\n"
                    func_code += "            environment_user_id = environment_user_ref or environment_user\n"
                func_code += f"        body = {{k: v for k, v in {{{body_items}}}.items() if v is not None}}\n"
                body_var = "body"

        # Confirmation check — include params + body so the LLM can render a
        # review table for provisioning / linking / snapshot workflows.
        func_code += f"        conf = check_confirmation('{method}', {endpoint_var}, action, '{tool_name}', confirmed or False, request_params=params, request_body={body_var})\n"
        func_code += f"        if conf:\n"
        func_code += f"            return conf\n"

        # Dispatch the request
        if details["has_filter"] and method == "POST":
            func_code += f"        return await make_api_request('{method}', {endpoint_var}, params=params, json_body=body)\n"
        elif method in ["POST", "PUT", "PATCH"] and body_var == "body":
            func_code += f"        return await make_api_request('{method}', {endpoint_var}, params=params, json_body=body if body else None)\n"
        else:
            func_code += f"        return await make_api_request('{method}', {endpoint_var}, params=params)\n"
    
    # Add else clause for unknown action
    func_code += "    else:\n"
    func_code += f"        return {{'error': f'Unknown action: {{action}}. Valid actions: {', '.join(actions_list)}'}}\n"
    func_code += "\n"
    
    return func_code


def _generate_legacy_tools_from_openapi():
    """Legacy function that generates separate tools per API. Kept for reference."""
    pass  # Removed - see git history for old implementation
