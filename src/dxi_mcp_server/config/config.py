"""
Configuration module for DCT MCP Server
"""

import os
import logging
from typing import Any, Dict, Optional


def _get_env(
    key: str, default: Optional[Any] = None, message: Optional[str] = None
) -> Any:
    """
    Get an environment variable, with an optional default.
    If no default is provided and the variable is not set, raise an error.
    """
    value = os.getenv(key)
    if value is None:
        if default is not None:
            return default
        if message is None:
            message = f"Required environment variable '{key}' is not set."
        raise ValueError(message)
    return value


def get_dct_config() -> Dict[str, Any]:
    """Get DCT configuration from environment variables"""

    api_key_error_msg = (
        "DCT_API_KEY environment variable is required. "
        "Please set it to your Delphix DCT API key."
    )

    config = {
        "api_key": _get_env("DCT_API_KEY", message=api_key_error_msg),
        "base_url": _get_env("DCT_BASE_URL", "https://localhost:8083"),
        "verify_ssl": _get_env("DCT_VERIFY_SSL", "false").lower() == "true",
        "timeout": int(_get_env("DCT_TIMEOUT", "30")),
        "max_retries": int(_get_env("DCT_MAX_RETRIES", "3")),
        "log_level": _get_env("DCT_LOG_LEVEL", "INFO").upper(),
    }

    # Validate log level
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if config["log_level"] not in valid_log_levels:
        raise ValueError(
            f"Invalid log level: {config['log_level']}. "
            f"Must be one of: {', '.join(valid_log_levels)}"
        )

    return config


def print_config_help():
    message = """
    Print configuration help
    Delphix DCT MCP Server Configuration:
    =====================================

    Required Environment Variables:
        DCT_API_KEY      Your DCT API key (required)

    Optional Environment Variables:
        DCT_BASE_URL     DCT base URL (default: https://localhost:8083)
        DCT_VERIFY_SSL   Verify SSL certificates (default: false)
        DCT_TIMEOUT      Request timeout in seconds (default: 30)
        DCT_MAX_RETRIES  Maximum retry attempts (default: 3)
        DCT_LOG_LEVEL    Logging level (default: INFO, options: DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example:
        export DCT_API_KEY=apk1.your-api-key-here
        export DCT_BASE_URL=https://your-dct-host:8083
        export DCT_VERIFY_SSL=true
        export DCT_LOG_LEVEL=DEBUG

    """
    print(message)


def setup_logging():
    log_level = os.getenv("DCT_LOG_LEVEL", "INFO").upper()
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=getattr(logging, log_level), format=log_format)

def verify_config():
    """Verify configuration and setup logging"""
    try:
        global app_config
        app_config = get_dct_config()
        setup_logging()
        logging.getLogger("dct-mcp-server").info("Configuration verified successfully.")
    except Exception as e:
        print(f"Configuration error: {str(e)}")
        print_config_help()
        exit(1)