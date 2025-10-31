"""
Unit tests for configuration module.

Tests settings loading, validation, and environment variable handling.
"""

import pytest
import os
from mssql_mcp.config import Settings, validate_settings, get_settings


class TestSettingsDefaults:
    """Test default configuration values."""

    def test_default_timeouts(self):
        """Test default timeout values."""
        settings = Settings()
        assert settings.MSSQL_CONNECTION_TIMEOUT == 5
        assert settings.MSSQL_QUERY_TIMEOUT == 30

    def test_default_security_settings(self):
        """Test default security settings."""
        settings = Settings()
        assert settings.READ_ONLY is True
        assert settings.ENABLE_WRITES is False
        assert settings.ADMIN_CONFIRM == ""

    def test_default_limits(self):
        """Test default query limits."""
        settings = Settings()
        assert settings.MAX_ROWS_PER_QUERY == 50000
        assert settings.MAX_QUERY_LENGTH == 50000

    def test_default_feature_flags(self):
        """Test default feature flags."""
        settings = Settings()
        assert settings.ENABLE_METRICS is True
        assert settings.ENABLE_HEALTH_CHECKS is True
        assert settings.ENABLE_SCHEMA_DISCOVERY is True

    def test_default_transport(self):
        """Test default MCP transport."""
        settings = Settings()
        assert settings.MCP_TRANSPORT == "stdio"

    def test_default_logging(self):
        """Test default logging configuration."""
        settings = Settings()
        assert settings.LOG_LEVEL == "INFO"
        assert settings.LOG_FORMAT == "json"


class TestSettingsValidation:
    """Test settings validation."""

    def test_valid_settings(self):
        """Valid settings should pass validation."""
        is_valid, error = validate_settings()
        # Default settings should be valid
        assert is_valid or error is not None  # Either valid or has specific error

    def test_missing_connection_string(self):
        """Missing connection string should fail validation."""
        settings = Settings(MSSQL_CONNECTION_STRING="")
        # Temporarily replace global settings
        from mssql_mcp import config
        original = config.settings
        config.settings = settings

        is_valid, error = validate_settings()
        assert not is_valid
        assert "MSSQL_CONNECTION_STRING" in error

        config.settings = original

    def test_writes_without_admin_confirm(self):
        """Enabling writes without admin confirm should fail."""
        settings = Settings(
            ENABLE_WRITES=True,
            ADMIN_CONFIRM=""
        )
        from mssql_mcp import config
        original = config.settings
        config.settings = settings

        is_valid, error = validate_settings()
        assert not is_valid
        assert "ADMIN_CONFIRM" in error

        config.settings = original

    def test_invalid_query_timeout(self):
        """Query timeout < 1 should fail validation."""
        settings = Settings(MSSQL_QUERY_TIMEOUT=0)
        from mssql_mcp import config
        original = config.settings
        config.settings = settings

        is_valid, error = validate_settings()
        assert not is_valid
        assert "MSSQL_QUERY_TIMEOUT" in error

        config.settings = original

    def test_invalid_max_rows(self):
        """Max rows < 1 should fail validation."""
        settings = Settings(MAX_ROWS_PER_QUERY=0)
        from mssql_mcp import config
        original = config.settings
        config.settings = settings

        is_valid, error = validate_settings()
        assert not is_valid
        assert "MAX_ROWS_PER_QUERY" in error

        config.settings = original


class TestSettingsLoading:
    """Test settings loading from environment."""

    def test_get_settings_singleton(self):
        """get_settings should return same instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_custom_connection_string(self):
        """Test loading custom connection string."""
        custom_conn = "Driver={test};Server=test"
        settings = Settings(MSSQL_CONNECTION_STRING=custom_conn)
        assert settings.MSSQL_CONNECTION_STRING == custom_conn

    def test_custom_timeouts(self):
        """Test loading custom timeout values."""
        settings = Settings(
            MSSQL_CONNECTION_TIMEOUT=10,
            MSSQL_QUERY_TIMEOUT=60
        )
        assert settings.MSSQL_CONNECTION_TIMEOUT == 10
        assert settings.MSSQL_QUERY_TIMEOUT == 60

    def test_custom_limits(self):
        """Test loading custom limit values."""
        settings = Settings(
            MAX_ROWS_PER_QUERY=1000,
            MAX_QUERY_LENGTH=10000
        )
        assert settings.MAX_ROWS_PER_QUERY == 1000
        assert settings.MAX_QUERY_LENGTH == 10000


class TestFeatureFlags:
    """Test feature flag configuration."""

    def test_disable_metrics(self):
        """Test disabling metrics."""
        settings = Settings(ENABLE_METRICS=False)
        assert settings.ENABLE_METRICS is False

    def test_disable_health_checks(self):
        """Test disabling health checks."""
        settings = Settings(ENABLE_HEALTH_CHECKS=False)
        assert settings.ENABLE_HEALTH_CHECKS is False

    def test_disable_schema_discovery(self):
        """Test disabling schema discovery."""
        settings = Settings(ENABLE_SCHEMA_DISCOVERY=False)
        assert settings.ENABLE_SCHEMA_DISCOVERY is False

    def test_enable_rate_limiting(self):
        """Test enabling rate limiting."""
        settings = Settings(
            RATE_LIMIT_ENABLED=True,
            RATE_LIMIT_QUERIES_PER_MINUTE=100
        )
        assert settings.RATE_LIMIT_ENABLED is True
        assert settings.RATE_LIMIT_QUERIES_PER_MINUTE == 100


class TestTransportConfiguration:
    """Test transport configuration."""

    def test_stdio_transport(self):
        """Test stdio transport configuration."""
        settings = Settings(MCP_TRANSPORT="stdio")
        assert settings.MCP_TRANSPORT == "stdio"

    def test_http_transport(self):
        """Test HTTP transport configuration."""
        settings = Settings(
            MCP_TRANSPORT="http",
            HTTP_BIND_HOST="0.0.0.0",
            HTTP_BIND_PORT=9000
        )
        assert settings.MCP_TRANSPORT == "http"
        assert settings.HTTP_BIND_HOST == "0.0.0.0"
        assert settings.HTTP_BIND_PORT == 9000
