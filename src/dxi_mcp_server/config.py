"""
Configuration module for DCT MCP Server
"""

import os
from typing import Any, Dict


def get_dct_config() -> Dict[str, Any]:
    """Get DCT configuration from environment variables"""

    config = {
        "api_key": os.getenv("DCT_API_KEY"),
        "base_url": os.getenv("DCT_BASE_URL", "https://localhost:8083"),
        "verify_ssl": os.getenv("DCT_VERIFY_SSL", "false").lower() == "true",
        "timeout": int(os.getenv("DCT_TIMEOUT", "30")),
        "max_retries": int(os.getenv("DCT_MAX_RETRIES", "3")),
        "log_level": os.getenv("DCT_LOG_LEVEL", "INFO").upper(),
    }

    # Validate required configuration
    if not config["api_key"]:
        raise ValueError(
            "DCT_API_KEY environment variable is required. "
            "Please set it to your Delphix DCT API key."
        )

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
