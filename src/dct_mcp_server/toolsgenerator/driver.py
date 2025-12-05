#!/usr/bin/env python3

"""
Driver code for the MCP server tool generation from Delphix DCT OpenAPI specification.

This script downloads the OpenAPI YAML specification from the DCT server,
parses it, and generates tool files for each API category defined in the
toolsgenerator/endpoints directory. Each tool file contains functions
corresponding to the API endpoints specified in the OpenAPI spec.

Generated tool files are saved in the dct_mcp_server/tools directory.
Each generated function includes:
- Function signature with parameters and types.
- Docstrings with parameter descriptions.
- Implementation using utility functions for making API requests.
"""


from textwrap import indent

import yaml
import os
import requests
import urllib3
import logging

TOOL_DIR = "src/dct_mcp_server/toolsgenerator/endpoints"
TOOLS_DIR = "src/dct_mcp_server/tools/"
APIS_TO_SUPPORT = {}
indent = 4

logger = logging.getLogger(__name__)

def load_api_endpoints():
    """Loads API endpoints from files in TOOL_DIR into APIS_TO_SUPPORT dict."""
    global APIS_TO_SUPPORT
    for file in os.listdir(TOOL_DIR):
        # Store the files as values of the dict with key as filename without _endpoints.txt
        if file.endswith("_endpoints.txt"):
            with open(os.path.join(TOOL_DIR, file), "r") as f:
                file_name = file.split(".")[0]
                APIS_TO_SUPPORT[file_name] = []
                for line in f:
                    APIS_TO_SUPPORT[file_name].append(line.strip())


def download_open_api_yaml(api_url: str, save_path: str):
    """Downloads the OpenAPI YAML from the given URL."""
    try:
        logger.info(f"Downloading OpenAPI spec from {api_url}...")
        
        # Insecure: Disabling SSL certificate verification for self-signed certs.
        response = requests.get(api_url, timeout=30, verify=False)
        response.raise_for_status()  # Raise an exception for bad status codes
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        logger.info(f"Successfully saved OpenAPI spec to {save_path}")
    except requests.exceptions.RequestException as e:
        logger.info(f"Error downloading OpenAPI spec: {e}")
        raise

translated_dict_for_types = {
    "integer": "int",
    "string": "str",
    "boolean": "bool",
    "float": "float",
}

prefix = """from mcp.server.fastmcp import FastMCP
from typing import Dict,Any,Optional
from ..core.decorators import log_tool_execution
import asyncio
import logging
import threading
from functools import wraps

client = None
logger = logging.getLogger(__name__)

def async_to_sync(async_func):
    \"\"\"Utility decorator to convert async functions to sync with proper event loop handling.\"\"\"
    @wraps(async_func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a task and run it synchronously
                result = None
                exception = None
                def run_in_thread():
                    nonlocal result, exception
                    try:
                        result = asyncio.run(async_func(*args, **kwargs))
                    except Exception as e:
                        exception = e
                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join()
                if exception:
                    raise exception
                return result
            else:
                return loop.run_until_complete(async_func(*args, **kwargs))
        except RuntimeError:
            return asyncio.run(async_func(*args, **kwargs))
    return wrapper

def make_api_request(method: str, endpoint: str, params: dict = None, json_body: dict = None):
    \"\"\"Utility function to make API requests with consistent parameter handling.\"\"\"
    @async_to_sync
    async def _make_request():
        return await client.make_request(method, endpoint, params=params or {}, json=json_body)
    return _make_request()

def build_params(**kwargs):
    \"\"\"Build parameters dictionary excluding None values.\"\"\"
    return {k: v for k, v in kwargs.items() if v is not None}

"""

def create_register_tool_function(apis):
    func_str = "\n"
    func_str += "def register_tools(app, dct_client):\n"
    func_str += " "*indent + "global client\n"
    func_str += " "*indent + "client = dct_client\n"
    func_str += " "*indent + "try:\n"
    for function in apis:
        func_str += " "*indent*2 + f"app.add_tool({function}, name=\"{function}\")\n"
    func_str += " "*indent + "except Exception as e:\n"
    func_str += " "*indent*2 + "logger.info(f\"Error registering tools: {e}\")\n"
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

def generate_tools_from_openapi():
    """Generates tool files from OpenAPI spec based on APIS_TO_SUPPORT."""
    load_api_endpoints()

    # Download the openapi yaml from application using client
    client_address = f"{os.getenv('DCT_BASE_URL')}/dct/static/api-external.yaml"
    API_FILE = "src/api.yaml"
    download_open_api_yaml(client_address, API_FILE)

    if client_address:
        logger.info(f"DCT_BASE_URL found: {client_address}")

    api_spec = read_open_api_yaml(API_FILE)
    logger.info("APIS to support loaded:", APIS_TO_SUPPORT)
    for tool_name, apis in APIS_TO_SUPPORT.items():
        TOOL_FILE = os.path.join(TOOLS_DIR, f"{tool_name}_tool.py")
        with open(TOOL_FILE, "w") as f:
            f.write(prefix)
        function_lists = []
        for api in apis:
            function_head = "@log_tool_execution\ndef "
            docstring = ""
            path_item = api_spec.get("paths", {}).get(api, {})
            # It could be get or post, handle if it is get or post
            operation = path_item.get("post", path_item.get("get"))
            if not operation:
                logger.info(f"No operation found for API: {api}")
                continue

            # Determine HTTP method
            http_method = "POST" if "post" in path_item else "GET"

            parameters = operation.get("parameters", {})
            function_head+= operation.get("operationId") + "("
            param_names = []
            function_lists.append(operation.get("operationId"))
            for param in parameters:
                if "$ref" in param:
                    param_def = resolve_ref(param["$ref"], api_spec)
                else:
                    param_def = param
                name = param_def.get("name", "unknown")
                try:
                    param_type = translated_dict_for_types[param_def['schema']['type']]
                    # Make limit and cursor optional parameters
                    required = param_def.get("required")
                    if not required:
                        function_head += f"{name}: Optional[{param_type}] = None, "
                    else:
                        function_head += f"{name}: {param_type}, "
                    param_names.append(name)
                except KeyError:
                    continue
                desc = param_def.get("description", "No description")
                docstring += " "*indent + f":param {name}: {desc}\n"
                required = param_def.get("required")
                if required:
                    required = "required"
                else:
                    required = "optional"
                docstring += " "*indent + f":param {name}: {desc}({required})\n"

            has_search_criteria = operation.get('x-filterable')
            if has_search_criteria:
                function_head+= "filter_expression: Optional[str] = None) -> Dict[str, Any]:\n"
                docstring += " "*indent + ":param filter_expression: Filter expression string (optional)\n"
            else:
                function_head = function_head.rstrip(", ") + ") -> Dict[str, Any]:\n"
            function_head+= " "*indent +"\"\"\"\n"+" "*indent +f"{operation.get('summary')}\n"
            responses = operation.get("responses", {})

            for status_code, details in responses.items():
                properties = details['content']['application/json']['schema']['properties']
                response_schema = resolve_ref(properties['items']['items']['$ref'], api_spec)
                docstring+=" "*indent + "Filter expression can include the following fields:\n"
                for prop_name, prop_def in response_schema.get("properties", {}).items():
                    prop_desc = prop_def.get("description", "No description")
                    docstring+= " "*indent +" - " + f"{prop_name}: {prop_desc}\n"
            if has_search_criteria:
                docstring += "\n" + " "*indent + "How to use filter_expresssion: \n"
                for line in api_spec['components']['requestBodies']['SearchBody']['description'].split('\n'):
                    docstring += " "*indent + f"{line}\n"
                # docstring += " "*indent + f"{api_spec['components']['requestBodies']['SearchBody']['description']}\n"

            # Generate function implementation using utility functions
            function_body = " "*indent + "# Build parameters excluding None values\n"

            if param_names:
                param_list = ", ".join([f"{name}={name}" for name in param_names])
                function_body += " "*indent + f"params = build_params({param_list})\n"
            else:
                function_body += " "*indent + "params = {}\n"

            if has_search_criteria and http_method == "POST":
                function_body += " "*indent + "search_body = {'filter_expression': filter_expression}\n"
                function_body += " "*indent + f"return make_api_request('{http_method}', '{api}', params=params, json_body=search_body)\n"
            else:
                function_body += " "*indent + f"return make_api_request('{http_method}', '{api}', params=params)\n"

            with open(TOOL_FILE, "a") as f:
                f.write(function_head+docstring+indent*" "+"\"\"\"\n"+function_body+"\n")

        with open(TOOL_FILE, "a") as f:
            f.write(create_register_tool_function(function_lists))
        # Delete the api.yaml file after generating all tools
    if os.path.exists(API_FILE):
        os.remove(API_FILE)
