"""
Configuration module for DCT MCP Server
"""

import logging
from pydantic import ValidationError
from .appconfig import AppConfig

# A global variable to hold the application configuration.
# It's initialized by the verify_config function.
app_config: AppConfig

def print_config_help():
    message = """
    Print configuration help
    Delphix DCT MCP Server Configuration:
    =====================================

    Required Environment Variables:
        DCT_API_KEY      Your DCT API key (required)
        DCT_BASE_URL     Base URL for the DCT API (required)
        DCT_PORT         Port number for the DCT API (required)

    Optional Environment Variables:
        DCT_VERIFY_SSL   Verify SSL certificates (default: false)
        DCT_TIMEOUT      Request timeout in seconds (default: 30)
        DCT_MAX_RETRIES  Maximum retry attempts (default: 3)
        LOG_LEVEL        Logging level (default: INFO, options: DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example:
        export DCT_API_KEY=apk1.your-api-key-here
        export DCT_BASE_URL=https://your-dct-host
        export DCT_PORT=8083
        export DCT_VERIFY_SSL=true
        export LOG_LEVEL=DEBUG

    """
    print(message)


def setup_logging(log_level: str):
    """
    Set up basic logging for the application.
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=log_level, format=log_format)

def verify_config():
    """
    Verify configuration by loading it from environment variables
    and set up logging.
    """
    try:
        global app_config
        # Pydantic's BaseSettings automatically reads from the environment
        # when the object is created. We are statically setting the 'name'.
        app_config = AppConfig(name="dlpx-server-app")
        setup_logging(app_config.log_level)
        logging.getLogger(app_config.name).info("Configuration verified successfully.")
    except ValidationError as e:
        print(f"Configuration error: {str(e)}")
        print_config_help()
        exit(1)