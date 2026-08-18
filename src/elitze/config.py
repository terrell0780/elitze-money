"""Application configuration via environment variables / .env file."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_Env = Literal["dev", "test", "prod"]


class Settings(BaseSettings):
    """Central settings. Every value is optional with a safe local default."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ELITZE_",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Runtime -----------------------------------------------------------
    env: _Env = "dev"

    # --- Storage -----------------------------------------------------------
    database_url: str | None = None  # None -> sqlite under data_dir
    qdrant_url: str | None = None  # None -> embedded local Qdrant
    qdrant_collection: str = "elitze_memory"

    # --- Model inference (NVIDIA NIM) -------------------------------------
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nim_api_key: SecretStr | None = None
    nim_model: str = "meta/llama-3.3-70b-instruct"
    llm_backend: Literal["auto", "nim", "dry"] = "auto"

    # --- Safety / policy ---------------------------------------------------
    max_experiment_budget: Decimal = Decimal("5000.00")
    max_daily_budget: Decimal = Decimal("10000.00")
    default_currency: str = "USD"

    # --- Revenue ingestion -------------------------------------------------
    webhook_secret: SecretStr | None = None

    # --- Serving -----------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- Directories -------------------------------------------------------
    data_dir: Path = Path("./data")
    vault_dir: Path = Path("./vault")

    # --- Orchestration -----------------------------------------------------
    max_iterations: int = 3

    # --- Misc --------------------------------------------------------------
    http_timeout_seconds: float = 20.0

    @field_validator("max_experiment_budget", "max_daily_budget", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: object) -> object:
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    # --- Derived helpers ---------------------------------------------------
    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.data_dir}/elitze.db"

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def is_test(self) -> bool:
        return self.env == "test"

    def resolve_paths(self) -> None:
        """Ensure runtime directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.vault_dir.mkdir(parents=True, exist_ok=True)

    def nim_api_key_plain(self) -> str | None:
        if self.nim_api_key is None:
            return None
        return self.nim_api_key.get_secret_value()

    def webhook_secret_plain(self) -> str | None:
        if self.webhook_secret is None:
            return None
        return self.webhook_secret.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def fresh_settings(**overrides: object) -> Settings:
    """Build a Settings instance with overrides (used by tests)."""
    settings = Settings(**overrides)
    settings.resolve_paths()
    return settings
