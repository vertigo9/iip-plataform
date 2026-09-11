"""IIP Configuration Manager."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class IIPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="IIP_", case_sensitive=False, extra="ignore"
    )

    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    app_name: str = "IIP Platform"
    version: str = "0.1.0-alpha"
    base_dir: Path = Field(default_factory=lambda: Path.cwd())
    log_level: str = "INFO"
    log_format: str = "json"
    obsidian_vault: Path = Field(default_factory=lambda: Path.cwd() / "vault")

    # Provider credentials. SecretStr keeps them out of repr()/logs — call
    # .get_secret_value() explicitly when the raw value is actually needed
    # (e.g. building an Authorization header). Maps from IIP_BOLSAI_API_KEY
    # / IIP_BRAPI_TOKEN via env_prefix, same names the CLI already used
    # directly from os.environ before this became a proper setting.
    bolsai_api_key: SecretStr | None = None
    brapi_token: SecretStr | None = None

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        return self.environment == Environment.TESTING


@lru_cache(maxsize=1)
def get_settings() -> IIPSettings:
    return IIPSettings()
