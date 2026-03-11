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
        "is_local_telemetry_enabled": os.getenv("IS_LOCAL_TELEMETRY_ENABLED", "false").lower()
        == "true",
        "toolset": os.getenv("DCT_TOOLSET", "self_service").lower().strip(),
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
    """Print configuration help"""
    print("\nDelphix DCT MCP Server Configuration:")
    print("=====================================")
    print()
    print("Required Environment Variables:")
    print("  DCT_API_KEY      Your DCT API key (required)")
    print()
    print("Optional Environment Variables:")
    print("  DCT_BASE_URL     DCT base URL (default: https://localhost:8083)")
    print("  DCT_VERIFY_SSL   Verify SSL certificates (default: false)")
    print("  DCT_TIMEOUT      Request timeout in seconds (default: 30)")
    print("  DCT_MAX_RETRIES  Maximum retry attempts (default: 3)")
    print(
        "  DCT_LOG_LEVEL    Logging level (default: INFO, options: DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    print(
        "  IS_LOCAL_TELEMETRY_ENABLED Enable local telemetry data collection (default: false)"
    )
    print(
        "  DCT_TOOLSET      Active toolset (default: self_service). Options:"
    )
    print(
        "                   - auto: Dynamic discovery mode with meta-tools"
    )
    print(
        "                   - self_service: Basic VDB operations for developers/QA"
    )
    print(
        "                   - self_service_provision: Extended self-service with provisioning"
    )
    print(
        "                   - continuous_data_admin: Full DBA/CD admin operations"
    )
    print(
        "                   - platform_admin: System administration tools"
    )
    print(
        "                   - reporting_insights: Read-only reporting and analytics"
    )
    print()
    print("Example:")
    print("  export DCT_API_KEY=apk1.your-api-key-here")
    print("  export DCT_BASE_URL=https://your-dct-host:8083")
    print("  export DCT_VERIFY_SSL=true")
    print("  export DCT_LOG_LEVEL=DEBUG")
    print("  export DCT_TOOLSET=self_service")
    print()
