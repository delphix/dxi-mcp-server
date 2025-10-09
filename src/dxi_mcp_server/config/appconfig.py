
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

# This is a generic, reusable model for API connection details.
# It inherits from BaseSettings to allow environment variable population.
class ApiDetails(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="forbid")

    api_key: str
    base_url: str
    port: int
    verify_ssl: bool = False
    timeout: int = 30
    max_retries: int = 3

# This is the main application configuration model.
class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="forbid")

    # Pydantic will automatically populate this from environment variables
    # with a 'DCT_' prefix because the field is named 'dct'.
    # e.g., DCT_API_KEY, DCT_BASE_URL
    dct: ApiDetails

    # General server settings can live here.
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    name: str