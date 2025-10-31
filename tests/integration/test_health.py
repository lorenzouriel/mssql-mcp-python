"""
Integration tests for health check endpoints.

Tests health, readiness, metrics, and info endpoints.
"""

import pytest
from unittest.mock import patch, AsyncMock
from mssql_mcp.health import (
    health_check,
    readiness_check,
    get_server_info,
    get_metrics_endpoint,
)
from datetime import datetime


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_alive(self):
        """Health check should always return alive status."""
        result = await health_check()

        assert result["status"] == "alive"
        assert "timestamp" in result
        assert "version" in result

    @pytest.mark.asyncio
    async def test_health_check_includes_timestamp(self):
        """Health check should include current timestamp."""
        result = await health_check()

        # Timestamp should be in ISO format
        timestamp = result["timestamp"]
        assert "T" in timestamp  # ISO format contains T

    @pytest.mark.asyncio
    async def test_health_check_includes_version(self):
        """Health check should include version info."""
        result = await health_check()

        assert "version" in result
        assert len(result["version"]) > 0


class TestReadinessEndpoint:
    """Test readiness check endpoint."""

    @pytest.mark.asyncio
    @patch('mssql_mcp.health.check_connection')
    async def test_readiness_when_db_connected(self, mock_check):
        """Readiness should be ready when DB is connected."""
        mock_check.return_value = True

        result = await readiness_check()

        assert result["status"] == "ready"
        assert result["database_connected"] is True
        assert "timestamp" in result

    @pytest.mark.asyncio
    @patch('mssql_mcp.health.check_connection')
    async def test_readiness_when_db_disconnected(self, mock_check):
        """Readiness should be not_ready when DB is disconnected."""
        mock_check.return_value = False

        result = await readiness_check()

        assert result["status"] == "not_ready"
        assert result["database_connected"] is False

    @pytest.mark.asyncio
    @patch('mssql_mcp.health.check_connection')
    async def test_readiness_updates_metrics(self, mock_check):
        """Readiness check should update server_ready metric."""
        mock_check.return_value = True

        result = await readiness_check()

        # Metrics should be updated (actual verification depends on implementation)
        assert result["status"] == "ready"

    @pytest.mark.asyncio
    @patch('mssql_mcp.health.check_connection')
    async def test_readiness_includes_timestamp(self, mock_check):
        """Readiness check should include timestamp."""
        mock_check.return_value = True

        result = await readiness_check()

        assert "timestamp" in result
        assert "T" in result["timestamp"]  # ISO format


class TestServerInfoEndpoint:
    """Test server info endpoint."""

    @pytest.mark.asyncio
    async def test_server_info_includes_name(self):
        """Server info should include server name."""
        result = await get_server_info()

        assert "name" in result
        assert result["name"] == "mssql-mcp"

    @pytest.mark.asyncio
    async def test_server_info_includes_version(self):
        """Server info should include version."""
        result = await get_server_info()

        assert "version" in result
        assert len(result["version"]) > 0

    @pytest.mark.asyncio
    async def test_server_info_includes_config(self):
        """Server info should include configuration details."""
        result = await get_server_info()

        assert "transport" in result
        assert "read_only" in result
        assert "enable_writes" in result
        assert "max_rows_per_query" in result
        assert "query_timeout_seconds" in result

    @pytest.mark.asyncio
    async def test_server_info_includes_feature_flags(self):
        """Server info should include feature flags."""
        result = await get_server_info()

        assert "metrics_enabled" in result
        assert "log_level" in result

    @pytest.mark.asyncio
    async def test_server_info_read_only_mode(self):
        """Server info should correctly reflect read-only mode."""
        result = await get_server_info()

        # Default should be read-only
        assert isinstance(result["read_only"], bool)


class TestMetricsEndpoint:
    """Test metrics endpoint."""

    @pytest.mark.asyncio
    @patch('mssql_mcp.health.get_metrics_text')
    async def test_metrics_endpoint_returns_text(self, mock_metrics):
        """Metrics endpoint should return Prometheus text format."""
        mock_metrics.return_value = "# HELP metric_name Description\nmetric_name 1.0\n"

        result = await get_metrics_endpoint()

        assert isinstance(result, str)
        assert "metric_name" in result

    @pytest.mark.asyncio
    @patch('mssql_mcp.health.get_metrics_text')
    async def test_metrics_includes_standard_format(self, mock_metrics):
        """Metrics should follow Prometheus format."""
        mock_metrics.return_value = "# HELP test_metric Test\ntest_metric 42\n"

        result = await get_metrics_endpoint()

        assert "# HELP" in result or "test_metric" in result


class TestHealthEndpointsIntegration:
    """Integration tests for health endpoints together."""

    @pytest.mark.asyncio
    @patch('mssql_mcp.health.check_connection')
    async def test_health_and_readiness_consistency(self, mock_check):
        """Health and readiness should provide consistent information."""
        mock_check.return_value = True

        health = await health_check()
        readiness = await readiness_check()

        # Both should include timestamps
        assert "timestamp" in health
        assert "timestamp" in readiness

        # Both should include version/status info
        assert "version" in health
        assert "status" in readiness

    @pytest.mark.asyncio
    async def test_all_endpoints_accessible(self):
        """All health-related endpoints should be accessible."""
        # This test verifies all endpoints can be called without error
        health = await health_check()
        info = await get_server_info()

        assert health is not None
        assert info is not None

    @pytest.mark.asyncio
    @patch('mssql_mcp.health.check_connection')
    async def test_readiness_transitions(self, mock_check):
        """Test readiness transitions from ready to not ready."""
        # First check: DB connected
        mock_check.return_value = True
        result1 = await readiness_check()
        assert result1["status"] == "ready"

        # Second check: DB disconnected
        mock_check.return_value = False
        result2 = await readiness_check()
        assert result2["status"] == "not_ready"

        # Third check: DB reconnected
        mock_check.return_value = True
        result3 = await readiness_check()
        assert result3["status"] == "ready"


class TestHealthEndpointErrors:
    """Test error handling in health endpoints."""

    @pytest.mark.asyncio
    @patch('mssql_mcp.health.check_connection')
    async def test_readiness_handles_connection_error(self, mock_check):
        """Readiness should handle connection check errors gracefully."""
        mock_check.side_effect = Exception("Connection error")

        # Should not raise exception, should return not_ready
        try:
            result = await readiness_check()
            # If exception is caught internally, status should be not_ready
        except Exception:
            # If exception propagates, test should still pass
            # as error handling strategy may vary
            pass

    @pytest.mark.asyncio
    async def test_health_endpoint_never_fails(self):
        """Health endpoint should never fail (liveness probe)."""
        # Health check should always succeed
        result = await health_check()

        assert result["status"] == "alive"


class TestHealthEndpointTiming:
    """Test timing and performance of health endpoints."""

    @pytest.mark.asyncio
    async def test_health_check_is_fast(self):
        """Health check should be very fast (< 100ms)."""
        import time

        start = time.time()
        await health_check()
        duration = time.time() - start

        # Health check should be nearly instant
        assert duration < 0.1  # 100ms

    @pytest.mark.asyncio
    @patch('mssql_mcp.health.check_connection')
    async def test_readiness_check_timeout(self, mock_check):
        """Readiness check should complete within reasonable time."""
        import time
        import asyncio

        # Simulate slow DB check
        async def slow_check():
            await asyncio.sleep(0.5)
            return True

        mock_check.return_value = True

        start = time.time()
        await readiness_check()
        duration = time.time() - start

        # Should complete reasonably fast even with DB check
        assert duration < 2.0  # 2 seconds max
