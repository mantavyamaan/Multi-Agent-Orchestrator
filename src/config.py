"""Runtime configuration — production-grade (report §5.11).

Uses pydantic-settings for:
  - Type coercion and validation of all env-var settings
  - Clear startup errors when required values are missing or invalid
  - No silent acceptance of nonsensical values (e.g. max_steps=0)
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Execution mode
    agent_mode: str = Field(default="mock", alias="AGENT_MODE")
    router_model_name: str = Field(default="gpt-4o-mini", alias="ROUTER_MODEL_NAME")
    worker_model_name: str = Field(default="gpt-4o", alias="WORKER_MODEL_NAME")
    model_provider: str = Field(default="openai", alias="MODEL_PROVIDER")

    # Independent termination mechanisms (§5.11)
    max_steps: int = Field(default=12, alias="MAX_STEPS")
    max_errors: int = Field(default=3, alias="MAX_ERRORS")
    max_consecutive_repeats: int = Field(default=3, alias="MAX_CONSECUTIVE_REPEATS")
    run_timeout_seconds: int = Field(default=180, alias="RUN_TIMEOUT_SECONDS")

    # API limits
    max_task_length: int = Field(default=2000)
    min_task_length: int = Field(default=10)
    rate_limit: str = Field(default="5/minute")

    @field_validator("max_steps", "max_errors", "max_consecutive_repeats", "run_timeout_seconds")
    @classmethod
    def must_be_positive(cls, v: int, info) -> int:
        if v <= 0:
            raise ValueError(f"{info.field_name} must be a positive integer, got {v}")
        return v

    @field_validator("agent_mode")
    @classmethod
    def valid_mode(cls, v: str) -> str:
        if v not in ("mock", "live"):
            raise ValueError(f"AGENT_MODE must be 'mock' or 'live', got '{v}'")
        return v

    @property
    def mode(self) -> str:
        """Alias for backward compatibility with existing code."""
        return self.agent_mode


settings = Settings()
