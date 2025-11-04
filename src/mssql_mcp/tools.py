"""
MCP Tools for MSSQL MCP Server.

Implements @mcp.tool() decorated functions that are exposed to MCP clients.
Each tool validates input, applies policies, executes DB queries, and returns results.
"""

import logging
import time
from typing import Optional, Any

from mcp.server.fastmcp import FastMCP

from .db import execute_query, execute_schema_query, get_database_info, check_connection, DatabaseError
from .policy import validate_with_audit, QueryMode, get_query_mode, explain_policy
from .metrics import MetricsContext, record_query_blocked
from .utils import format_table, format_json, result_summary

logger = logging.getLogger(__name__)

# Create MCP server instance
mcp = FastMCP("mssql-mcp")


@mcp.tool()
async def execute_sql(
    sql: str,
    format: str = "table",
) -> str:
    """
    Execute a SQL query against the SQL Server database.

    This tool executes SELECT queries by default (read-only mode). If write operations
    are enabled in config, INSERT/UPDATE/DELETE are allowed.

    Args:
        sql: SQL query to execute (typically SELECT)
        format: Output format - 'table', 'json', or 'csv' (default: 'table')

    Returns:
        Formatted query results as string
    """
    client_id = "unknown"  # Could be extracted from request context in production
    tool_name = "execute_sql"

    start_time = time.time()

    # Validate policy
    is_allowed, reason = validate_with_audit(sql, client_id=client_id, tool_name=tool_name)
    if not is_allowed:
        record_query_blocked(reason or "unknown")
        return f"ERROR: Query not allowed - {reason}"

    # Execute query with metrics tracking
    with MetricsContext(tool_name) as metrics:
        try:
            columns, rows = await execute_query(sql)
            metrics.set_rows(len(rows))

            # Format output
            if format.lower() == "json":
                result = format_json(columns, rows)
            elif format.lower() == "csv":
                from .utils import format_csv
                result = format_csv(columns, rows)
            else:  # table (default)
                result = format_table(columns, rows) if columns else "(no result)"

            # Add summary
            summary = result_summary(columns, rows)
            return f"{result}\n\n[{summary}]"

        except Exception as e:
            logger.exception("Query execution failed")
            return f"ERROR: {type(e).__name__}: {str(e)}"


@mcp.tool()
async def list_schemas() -> str:
    """
    List all schemas in the current database.

    Returns:
        Formatted list of schema names
    """
    tool_name = "list_schemas"

    with MetricsContext(tool_name) as metrics:
        try:
            sql = """
            SELECT
                schema_id,
                name,
                principal_id
            FROM sys.schemas
            ORDER BY name
            """
            columns, rows = await execute_schema_query(sql)
            metrics.set_rows(len(rows))

            if not rows:
                return "No schemas found."

            # Format simple list
            schema_names = [row[1] for row in rows]
            return "\n".join(f"  - {name}" for name in schema_names)

        except Exception as e:
            logger.exception("list_schemas failed")
            return f"ERROR: {type(e).__name__}: {str(e)}"


@mcp.tool()
async def list_tables(schema: Optional[str] = None, limit: int = 200) -> str:
    """
    List tables in the database, optionally filtered by schema.

    Args:
        schema: Optional schema name to filter (default: all schemas)
        limit: Maximum number of tables to return (default: 200)

    Returns:
        Formatted list of tables
    """
    tool_name = "list_tables"

    if limit < 1:
        return "ERROR: limit must be >= 1"
    if limit > 1000:
        limit = 1000  # Cap at 1000

    with MetricsContext(tool_name) as metrics:
        try:
            if schema:
                # Validate schema name to prevent injection
                from .utils import escape_sql_string
                schema_filter = f"AND s.name = {escape_sql_string(schema)}"
            else:
                schema_filter = ""

            sql = f"""
            SELECT TOP {limit}
                s.name as schema_name,
                t.name as table_name,
                t.object_id
            FROM sys.tables t
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE t.type = 'U'  -- User tables only
            {schema_filter}
            ORDER BY s.name, t.name
            """

            columns, rows = await execute_schema_query(sql)
            metrics.set_rows(len(rows))

            if not rows:
                return "No tables found."

            # Format results
            result = format_table(columns, rows)
            return f"{result}\n\n[{len(rows)} table(s)]"

        except Exception as e:
            logger.exception("list_tables failed")
            return f"ERROR: {type(e).__name__}: {str(e)}"


@mcp.tool()
async def schema_discovery(schema: Optional[str] = None) -> str:
    """
    Discover schema information: tables, columns, types, and constraints.

    Returns detailed metadata about database objects as JSON.

    Args:
        schema: Optional schema name to filter (default: all schemas)

    Returns:
        JSON-formatted schema metadata
    """
    tool_name = "schema_discovery"

    with MetricsContext(tool_name) as metrics:
        try:
            if schema:
                from .utils import escape_sql_string
                schema_filter = f"WHERE s.name = {escape_sql_string(schema)}"
            else:
                schema_filter = ""

            sql = f"""
            SELECT
                s.name as schema_name,
                t.name as table_name,
                c.name as column_name,
                ty.name as column_type,
                c.max_length,
                c.precision,
                c.scale,
                c.is_nullable,
                CASE WHEN c.column_id IS NOT NULL THEN 1 ELSE 0 END as has_default,
				ep.value as table_description
            FROM sys.schemas s
            INNER JOIN sys.tables t ON s.schema_id = t.schema_id
            INNER JOIN sys.columns c ON t.object_id = c.object_id
            INNER JOIN sys.types ty ON c.user_type_id = ty.user_type_id
			LEFT JOIN sys.extended_properties ep ON ep.major_id = c.object_id AND ep.minor_id = c.column_id
            {schema_filter}
            ORDER BY schema_name, table_name, column_name
            """

            columns, rows = await execute_schema_query(sql, timeout=60)
            metrics.set_rows(len(rows))

            if not rows:
                return "No schema information found."

            # Convert to JSON structure
            from .utils import format_json
            result = format_json(columns, rows)
            return result

        except Exception as e:
            logger.exception("schema_discovery failed")
            return f"ERROR: {type(e).__name__}: {str(e)}"


@mcp.tool()
async def get_database_info() -> str:
    """
    Get general information about the database and server.

    Returns:
        JSON-formatted database information
    """
    tool_name = "get_database_info"

    with MetricsContext(tool_name) as metrics:
        try:
            info = await get_database_info()
            metrics.set_rows(1)

            from .utils import format_json
            # Convert dict to JSON-like format
            result = format_json(
                list(info.keys()),
                [tuple(info.values())]
            )
            return result

        except Exception as e:
            logger.exception("get_database_info failed")
            return f"ERROR: {type(e).__name__}: {str(e)}"


@mcp.tool()
async def get_policy_info() -> str:
    """
    Get current policy and safety settings.

    Returns:
        JSON-formatted policy information
    """
    tool_name = "get_policy_info"

    with MetricsContext(tool_name) as metrics:
        try:
            policy = explain_policy()
            metrics.set_rows(1)

            import json
            return json.dumps(policy, indent=2)

        except Exception as e:
            logger.exception("get_policy_info failed")
            return f"ERROR: {type(e).__name__}: {str(e)}"


@mcp.tool()
async def check_db_connection() -> str:
    """
    Check if the database connection is active and healthy.

    Returns:
        Connection status message
    """
    tool_name = "check_db_connection"

    with MetricsContext(tool_name) as metrics:
        try:
            is_connected = await check_connection()
            metrics.set_rows(1)

            if is_connected:
                return "✓ Database connection is healthy"
            else:
                return "✗ Database connection failed"

        except Exception as e:
            logger.exception("check_db_connection failed")
            return f"ERROR: Database connection check failed - {str(e)}"
