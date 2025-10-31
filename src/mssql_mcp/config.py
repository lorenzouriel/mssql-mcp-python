"""
Configuration module for MSSQL MCP Server.

Loads settings from environment variables using Pydantic BaseSettings.
Supports .env file for local development.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database connection
    MSSQL_CONNECTION_STRING: str 
    MSSQL_CONNECTION_TIMEOUT: int = 30  # seconds
    MSSQL_QUERY_TIMEOUT: int = 30  # seconds
    MSSQL_MAX_POOL_SIZE: int = 10

    # Security & safety
    READ_ONLY: bool = True
    ENABLE_WRITES: bool = False
    ADMIN_CONFIRM: str = ""  # must be set to a specific token to enable writes
    MAX_ROWS_PER_QUERY: int = 50000
    MAX_QUERY_LENGTH: int = 50000  # characters

    # Feature flags
    ENABLE_METRICS: bool = True
    ENABLE_HEALTH_CHECKS: bool = True
    ENABLE_SCHEMA_DISCOVERY: bool = True

    # Server configuration
    MCP_TRANSPORT: str = "stdio"  # 'stdio' or 'http'
    HTTP_BIND_HOST: str = "127.0.0.1"
    HTTP_BIND_PORT: int = 8080

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # 'json' or 'text'

    # Observability
    ENABLE_PROMETHEUS: bool = True
    SENTRY_DSN: Optional[str] = None

    # Rate limiting
    RATE_LIMIT_QUERIES_PER_MINUTE: int = 1000
    RATE_LIMIT_ENABLED: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        frozen=False,
    )


# Global settings singleton
settings = Settings()


def get_settings() -> Settings:
    """Get global settings instance."""
    return settings


def validate_settings() -> tuple[bool, Optional[str]]:
    """
    Validate critical settings. Returns (is_valid, error_message).
    """
    if not settings.MSSQL_CONNECTION_STRING:
        return False, "MSSQL_CONNECTION_STRING must be set"

    if settings.ENABLE_WRITES and not settings.ADMIN_CONFIRM:
        return False, "ADMIN_CONFIRM must be set to enable writes"

    if settings.MSSQL_QUERY_TIMEOUT < 1:
        return False, "MSSQL_QUERY_TIMEOUT must be >= 1 second"

    if settings.MAX_ROWS_PER_QUERY < 1:
        return False, "MAX_ROWS_PER_QUERY must be >= 1"

    return True, None
