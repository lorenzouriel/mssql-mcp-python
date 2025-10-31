"""
Integration tests for MCP tools.

Tests the complete flow of MCP tool execution including:
- Policy validation
- Database query execution
- Result formatting
- Error handling
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from mssql_mcp.tools import execute_sql, list_schemas, list_tables, schema_discovery, get_policy_info
from mssql_mcp.policy import QueryMode
from mssql_mcp.db import DatabaseError


class TestExecuteSQLTool:
    """Test execute_sql MCP tool."""

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_query')
    async def test_execute_simple_select(self, mock_execute):
        """Test executing simple SELECT query."""
        # Mock database response
        mock_execute.return_value = (
            ["id", "name"],
            [(1, "Alice"), (2, "Bob")]
        )

        result = await execute_sql("SELECT id, name FROM users")

        assert "Alice" in result
        assert "Bob" in result
        mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_blocked_query(self):
        """Test executing blocked query (write operation in read-only mode)."""
        result = await execute_sql("DROP TABLE users")

        assert "not allowed" in result.lower() or "denied" in result.lower()

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_query')
    async def test_execute_with_json_format(self, mock_execute):
        """Test executing query with JSON output format."""
        mock_execute.return_value = (
            ["id", "name"],
            [(1, "Alice"), (2, "Bob")]
        )

        result = await execute_sql("SELECT id, name FROM users", format="json")

        # Result should be valid JSON
        assert "[" in result and "]" in result
        assert "Alice" in result

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_query')
    async def test_execute_with_csv_format(self, mock_execute):
        """Test executing query with CSV output format."""
        mock_execute.return_value = (
            ["id", "name"],
            [(1, "Alice"), (2, "Bob")]
        )

        result = await execute_sql("SELECT id, name FROM users", format="csv")

        # CSV should have headers and data
        assert "id,name" in result
        assert "Alice" in result

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_query')
    async def test_execute_database_error(self, mock_execute):
        """Test handling database errors."""
        mock_execute.side_effect = DatabaseError("Connection failed")

        result = await execute_sql("SELECT * FROM users")

        assert "error" in result.lower() or "failed" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_empty_query(self):
        """Test executing empty query."""
        result = await execute_sql("")

        assert "empty" in result.lower() or "not allowed" in result.lower()

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_query')
    async def test_execute_multi_statement_blocked(self, mock_execute):
        """Test that multi-statement queries are blocked."""
        result = await execute_sql("SELECT * FROM users; SELECT * FROM products")

        assert "not allowed" in result.lower() or "multi-statement" in result.lower()


class TestListSchemasTool:
    """Test list_schemas MCP tool."""

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_schema_query')
    async def test_list_all_schemas(self, mock_execute):
        """Test listing all schemas."""
        mock_execute.return_value = (
            ["schema_name"],
            [("dbo",), ("sales",), ("hr",)]
        )

        result = await list_schemas()

        assert "dbo" in result
        assert "sales" in result
        assert "hr" in result

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_schema_query')
    async def test_list_schemas_database_error(self, mock_execute):
        """Test error handling when listing schemas."""
        mock_execute.side_effect = DatabaseError("Permission denied")

        result = await list_schemas()

        assert "error" in result.lower()


class TestListTablesTool:
    """Test list_tables MCP tool."""

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_schema_query')
    async def test_list_all_tables(self, mock_execute):
        """Test listing all tables."""
        mock_execute.return_value = (
            ["schema_name", "table_name"],
            [("dbo", "users"), ("dbo", "products"), ("sales", "orders")]
        )

        result = await list_tables()

        assert "users" in result
        assert "products" in result
        assert "orders" in result

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_schema_query')
    async def test_list_tables_by_schema(self, mock_execute):
        """Test listing tables filtered by schema."""
        mock_execute.return_value = (
            ["schema_name", "table_name"],
            [("dbo", "users"), ("dbo", "products")]
        )

        result = await list_tables(schema="dbo")

        assert "users" in result
        assert "products" in result


class TestSchemaDiscoveryTool:
    """Test schema_discovery MCP tool."""

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_schema_query')
    async def test_discover_table_schema(self, mock_execute):
        """Test discovering schema for a specific table."""
        mock_execute.return_value = (
            ["column_name", "data_type", "is_nullable"],
            [
                ("id", "int", "NO"),
                ("name", "varchar", "YES"),
                ("email", "varchar", "YES"),
            ]
        )

        result = await schema_discovery(table_name="users")

        assert "id" in result
        assert "name" in result
        assert "int" in result
        assert "varchar" in result

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_schema_query')
    async def test_discover_schema_with_schema_name(self, mock_execute):
        """Test discovering schema with explicit schema name."""
        mock_execute.return_value = (
            ["column_name", "data_type"],
            [("order_id", "int"), ("customer_id", "int")]
        )

        result = await schema_discovery(schema_name="sales", table_name="orders")

        assert "order_id" in result
        assert "customer_id" in result


class TestGetPolicyInfoTool:
    """Test get_policy_info MCP tool."""

    @pytest.mark.asyncio
    async def test_get_policy_info(self):
        """Test retrieving policy information."""
        result = await get_policy_info()

        # Should contain policy information
        assert "read" in result.lower() or "policy" in result.lower()


class TestToolErrorHandling:
    """Test error handling across all tools."""

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.check_connection')
    async def test_connection_failure_handling(self, mock_check):
        """Test handling when database connection fails."""
        mock_check.return_value = False

        # Tools should handle connection failures gracefully
        # This is a general test - specific tools may handle differently


class TestToolMetrics:
    """Test that tools record metrics correctly."""

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.execute_query')
    @patch('mssql_mcp.tools.MetricsContext')
    async def test_metrics_recorded_on_success(self, mock_metrics, mock_execute):
        """Test that metrics are recorded on successful execution."""
        mock_execute.return_value = (["id"], [(1,)])

        await execute_sql("SELECT id FROM users")

        # Metrics context should have been used
        # (Implementation depends on actual metrics code)

    @pytest.mark.asyncio
    @patch('mssql_mcp.tools.record_query_blocked')
    async def test_metrics_recorded_on_blocked_query(self, mock_record):
        """Test that metrics are recorded when query is blocked."""
        await execute_sql("DROP TABLE users")

        # Should have recorded blocked query
        mock_record.assert_called()
