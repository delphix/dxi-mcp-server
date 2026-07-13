"""
Configuration module for DCT MCP Server
"""

import os
from typing import Any, Dict


def get_dct_config(require_key: bool = True) -> Dict[str, Any]:
    """Get DCT configuration from environment variables"""
    import tempfile

    _default_spec_cache_path = os.path.join(
        tempfile.gettempdir(), "dct_mcp_tools", "api-external-dynamic.yaml"
    )

    config = {
        "api_key": os.getenv("DCT_API_KEY"),
        "base_url": os.getenv("DCT_BASE_URL", "https://localhost:8083"),
        "verify_ssl": os.getenv("DCT_VERIFY_SSL", "false").lower() == "true",
        "timeout": int(os.getenv("DCT_TIMEOUT", "30")),
        "max_retries": int(os.getenv("DCT_MAX_RETRIES", "3")),
        "log_level": os.getenv("DCT_LOG_LEVEL", "INFO").upper(),
        "is_local_telemetry_enabled": os.getenv(
            "IS_LOCAL_TELEMETRY_ENABLED", "false"
        ).lower()
        == "true",
        "toolset": os.getenv("DCT_TOOLSET", "dynamic").lower().strip(),
        # Dynamic mode (DCT_TOOLSET=dynamic) spec cache settings
        "spec_cache_path": os.getenv("DCT_SPEC_CACHE_PATH", _default_spec_cache_path),
        "spec_max_age_hours": int(os.getenv("DCT_SPEC_MAX_AGE_HOURS", "24")),
        "transport": os.getenv("DCT_TRANSPORT", "stdio").lower().strip(),
        "auth_mode": os.getenv("DCT_AUTH_MODE", "standalone").lower().strip(),
        "http_host": os.getenv("DCT_HTTP_HOST", "127.0.0.1"),
        "http_port": int(os.getenv("DCT_HTTP_PORT", "8765")),
        "require_tls": os.getenv("DCT_REQUIRE_TLS", "true").lower() == "true",
    }

    # Validate required configuration
    if not config["api_key"] and config["auth_mode"] != "embedded" and require_key:
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

    # Validate transport
    if config["transport"] not in ("stdio", "http"):
        raise ValueError(
            f"Invalid DCT_TRANSPORT: {config['transport']}. "
            "Must be one of: stdio, http"
        )

    # Validate auth_mode
    if config["auth_mode"] not in ("standalone", "embedded"):
        raise ValueError(
            f"Invalid DCT_AUTH_MODE: {config['auth_mode']}. "
            "Must be one of: standalone, embedded"
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
    print("  DCT_TOOLSET      Active toolset (default: dynamic). Options:")
    print(
        "                   - dynamic: 2-tool mode (discovery + execute) driven by live OpenAPI spec (default)"
    )
    print("                   - self_service: Basic VDB operations for developers/QA")
    print(
        "                   - self_service_provision: Extended self-service with provisioning"
    )
    print("                   - continuous_data_admin: Full DBA/CD admin operations")
    print("                   - platform_admin: System administration tools")
    print("                   - reporting_insights: Read-only reporting and analytics")
    print()
    print("Transport and auth optional variables:")
    print(
        "  DCT_TRANSPORT    Server transport mode (default: stdio, options: stdio, http)"
    )
    print(
        "  DCT_AUTH_MODE    Authentication mode (default: standalone, options: standalone, embedded)"
    )
    print(
        "                   In 'embedded' mode, DCT_API_KEY is not required (auth is handled externally)"
    )
    print(
        "  DCT_HTTP_HOST    Host to bind when DCT_TRANSPORT=http (default: 127.0.0.1)"
    )
    print(
        "  DCT_HTTP_PORT    Port to bind when DCT_TRANSPORT=http (default: 8765)"
    )
    print(
        "  DCT_REQUIRE_TLS  Require TLS when DCT_TRANSPORT=http (default: true)"
    )
    print()
    print("Dynamic mode (DCT_TOOLSET=dynamic) optional variables:")
    print(
        "  DCT_SPEC_CACHE_PATH     Path to cache the downloaded OpenAPI spec "
        "(default: $TEMP/dct_mcp_tools/api-external-dynamic.yaml)"
    )
    print(
        "  DCT_SPEC_MAX_AGE_HOURS  Hours before re-downloading the spec (default: 24)"
    )
    print()
    print("Example:")
    print("  export DCT_API_KEY=apk1.your-api-key-here")
    print("  export DCT_BASE_URL=https://your-dct-host:8083")
    print("  export DCT_VERIFY_SSL=true")
    print("  export DCT_LOG_LEVEL=DEBUG")
    print("  export DCT_TOOLSET=self_service")
    print("  export DCT_TRANSPORT=http")
    print("  export DCT_AUTH_MODE=standalone")
    print()
