"""
MCP Tools for MSSQL MCP Server.

Implements @mcp.tool() decorated functions that are exposed to MCP clients.
Each tool validates input, applies policies, executes DB queries, and returns results.
"""

import base64
import logging
import time
from typing import Optional, Any

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.transport_security import TransportSecuritySettings

from .config import settings

from .db import execute_query, execute_schema_query, get_database_info as fetch_database_info, check_connection, DatabaseError, request_credentials
from .policy import validate_with_audit, QueryMode, get_query_mode, explain_policy
from .metrics import MetricsContext, record_query_blocked
from .utils import format_table, format_json, result_summary

logger = logging.getLogger(__name__)


# HTTP headers a remote client may send (e.g. in its MCP config) to authenticate
# as its own SQL login for the duration of a request, overriding the server's
# default credentials. Passwords travel in headers, so use HTTPS / a trusted
# network in production.
#
# HTTP header values must be Latin-1 (bytes 0-255), so a value with non-ASCII
# characters (e.g. accented passwords) cannot be sent raw — many clients refuse
# to. For those, send the base64 of the UTF-8 value in the "<header>-B64" variant
# instead; it takes precedence over the plain header.
_HDR_USER = "X-MSSQL-User"
_HDR_PASSWORD = "X-MSSQL-Password"
_HDR_TRUSTED = "X-MSSQL-Trusted-Connection"
_B64_SUFFIX = "-B64"


def _header_value(headers, name: str) -> Optional[str]:
    """Return a header's value, preferring its base64 variant (<name>-B64).

    The base64 form lets clients pass values containing non-Latin-1 characters,
    which raw HTTP headers cannot carry.
    """
    b64 = headers.get(name + _B64_SUFFIX)
    if b64:
        try:
            return base64.b64decode(b64).decode("utf-8")
        except Exception:
            logger.warning("Ignoring malformed base64 header: %s", name + _B64_SUFFIX)
            return None
    return headers.get(name)


def _creds_from_ctx(ctx: Optional[Context]) -> dict:
    """Extract optional per-request SQL credentials from the MCP request headers.

    Returns a dict suitable for request_credentials(**...); empty when none are
    provided (e.g. stdio transport, or a client that sends no credential headers).
    """
    if ctx is None:
        return {}
    try:
        request = ctx.request_context.request
    except Exception:
        return {}
    headers = getattr(request, "headers", None)
    if not headers:
        return {}

    creds: dict = {}
    user = _header_value(headers, _HDR_USER)
    password = _header_value(headers, _HDR_PASSWORD)
    trusted_raw = _header_value(headers, _HDR_TRUSTED)
    if user:
        creds["user"] = user
    if password:
        creds["password"] = password
    if trusted_raw is not None:
        creds["trusted"] = trusted_raw.strip().lower() in ("1", "true", "yes", "on")
    return creds

def _get_transport_security():
    """Configure transport security based on ALLOWED_HOST setting."""
    allowed_hosts = ["localhost:*", "127.0.0.1:*"]
    allowed_origins = ["http://localhost:*", "http://127.0.0.1:*"]
    
    if settings.ALLOWED_HOST:
        allowed_hosts.append(f"{settings.ALLOWED_HOST}:*")
        allowed_origins.append(f"http://{settings.ALLOWED_HOST}:*")
    
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )

# Create MCP server instance with transport security
mcp = FastMCP("mssql-mcp", transport_security=_get_transport_security())


@mcp.tool()
async def execute_sql(
    sql: str,
    format: str = "table",
    timeout: Optional[int] = None,
    max_rows: Optional[int] = None,
    ctx: Optional[Context] = None,
) -> str:
    """
    Execute a SQL statement against the SQL Server database.

    SELECT queries run in read-only mode by default. Write operations
    (INSERT/UPDATE/DELETE) only succeed if the server is started with
    ENABLE_WRITES=true and a matching ADMIN_CONFIRM token; otherwise they are
    rejected by the policy engine. For writes, the affected-row count is returned.

    Args:
        sql: SQL statement to execute.
        format: Output format for result sets - 'table', 'json', or 'csv'
            (default: 'table'). Use 'json' for the most machine-readable output.
        timeout: Per-query timeout in seconds. Overrides the server default
            (MSSQL_QUERY_TIMEOUT) for this call only — raise it for slow,
            complex queries such as large JOINs or CROSS APPLY.
        max_rows: Maximum rows to return for this call. Overrides the server
            default (MAX_ROWS_PER_QUERY). The output flags when results are
            truncated.

    Returns:
        Formatted query results as string, followed by a summary line. For write
        statements, a confirmation with the affected-row count.
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
            with request_credentials(**_creds_from_ctx(ctx)):
                res = await execute_query(sql, timeout=timeout, max_rows=max_rows)
            metrics.set_rows(len(res.rows))

            # Write statement / no result set: report affected rows.
            if not res.columns:
                if res.rowcount >= 0:
                    return f"OK: {res.rowcount} row(s) affected."
                return "OK: statement executed (no result set)."

            # Format output
            if format.lower() == "json":
                result = format_json(res.columns, res.rows)
            elif format.lower() == "csv":
                from .utils import format_csv
                result = format_csv(res.columns, res.rows)
            else:  # table (default)
                result = format_table(res.columns, res.rows)

            # Add summary, flagging truncation explicitly so it is never silent.
            summary = result_summary(res.columns, res.rows)
            if res.truncated:
                summary += " — TRUNCATED (more rows available; raise max_rows to see them)"
            return f"{result}\n\n[{summary}]"

        except Exception as e:
            logger.exception("Query execution failed")
            return f"ERROR: {type(e).__name__}: {str(e)}"


@mcp.tool()
async def list_schemas(ctx: Optional[Context] = None) -> str:
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
            with request_credentials(**_creds_from_ctx(ctx)):
                res = await execute_schema_query(sql)
            metrics.set_rows(len(res.rows))

            if not res.rows:
                return "No schemas found."

            # Format simple list
            schema_names = [row[1] for row in res.rows]
            return "\n".join(f"  - {name}" for name in schema_names)

        except Exception as e:
            logger.exception("list_schemas failed")
            return f"ERROR: {type(e).__name__}: {str(e)}"


@mcp.tool()
async def list_tables(schema: Optional[str] = None, limit: int = 200, ctx: Optional[Context] = None) -> str:
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

            with request_credentials(**_creds_from_ctx(ctx)):
                res = await execute_schema_query(sql)
            metrics.set_rows(len(res.rows))

            if not res.rows:
                return "No tables found."

            # Format results
            result = format_table(res.columns, res.rows)
            return f"{result}\n\n[{len(res.rows)} table(s)]"

        except Exception as e:
            logger.exception("list_tables failed")
            return f"ERROR: {type(e).__name__}: {str(e)}"


@mcp.tool()
async def schema_discovery(schema: Optional[str] = None, ctx: Optional[Context] = None) -> str:
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

            with request_credentials(**_creds_from_ctx(ctx)):
                res = await execute_schema_query(sql, timeout=60)
            metrics.set_rows(len(res.rows))

            if not res.rows:
                return "No schema information found."

            # Convert to JSON structure
            from .utils import format_json
            result = format_json(res.columns, res.rows)
            return result

        except Exception as e:
            logger.exception("schema_discovery failed")
            return f"ERROR: {type(e).__name__}: {str(e)}"


@mcp.tool()
async def describe_table(table: str, ctx: Optional[Context] = None) -> str:
    """
    Describe a single table's structure: columns, data types, length,
    nullability, primary-key membership, and column descriptions.

    A focused alternative to schema_discovery when you only need one table.

    Args:
        table: Table name, optionally schema-qualified (e.g. 'dbo.users' or
            'users'). Without a schema prefix, all schemas are matched.

    Returns:
        JSON-formatted column metadata, or a not-found message.
    """
    tool_name = "describe_table"
    from .utils import escape_sql_string, format_json

    # Split optional schema qualifier ('schema.table').
    if "." in table:
        schema_name, table_name = table.split(".", 1)
    else:
        schema_name, table_name = None, table

    with MetricsContext(tool_name) as metrics:
        try:
            filters = [f"t.name = {escape_sql_string(table_name)}"]
            if schema_name:
                filters.append(f"s.name = {escape_sql_string(schema_name)}")
            where = " AND ".join(filters)

            sql = f"""
            SELECT
                s.name AS schema_name,
                t.name AS table_name,
                c.column_id,
                c.name AS column_name,
                ty.name AS data_type,
                c.max_length,
                c.precision,
                c.scale,
                c.is_nullable,
                CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key,
                ep.value AS description
            FROM sys.tables t
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            INNER JOIN sys.columns c ON t.object_id = c.object_id
            INNER JOIN sys.types ty ON c.user_type_id = ty.user_type_id
            LEFT JOIN (
                SELECT ic.object_id, ic.column_id
                FROM sys.index_columns ic
                INNER JOIN sys.indexes i
                    ON ic.object_id = i.object_id AND ic.index_id = i.index_id
                WHERE i.is_primary_key = 1
            ) pk ON pk.object_id = c.object_id AND pk.column_id = c.column_id
            LEFT JOIN sys.extended_properties ep
                ON ep.major_id = c.object_id AND ep.minor_id = c.column_id
            WHERE {where}
            ORDER BY s.name, t.name, c.column_id
            """
            with request_credentials(**_creds_from_ctx(ctx)):
                res = await execute_schema_query(sql)
            metrics.set_rows(len(res.rows))

            if not res.rows:
                return f"Table not found: {table}"

            return format_json(res.columns, res.rows)

        except Exception as e:
            logger.exception("describe_table failed")
            return f"ERROR: {type(e).__name__}: {str(e)}"


@mcp.tool()
async def get_database_info(ctx: Optional[Context] = None) -> str:
    """
    Get general information about the database and server.

    Returns:
        JSON-formatted database information
    """
    tool_name = "get_database_info"

    with MetricsContext(tool_name) as metrics:
        try:
            with request_credentials(**_creds_from_ctx(ctx)):
                info = await fetch_database_info()
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
async def check_db_connection(ctx: Optional[Context] = None) -> str:
    """
    Check if the database connection is active and healthy.

    Returns:
        Connection status message
    """
    tool_name = "check_db_connection"

    with MetricsContext(tool_name) as metrics:
        try:
            with request_credentials(**_creds_from_ctx(ctx)):
                is_connected = await check_connection()
            metrics.set_rows(1)

            if is_connected:
                return "✓ Database connection is healthy"
            else:
                return "✗ Database connection failed"

        except Exception as e:
            logger.exception("check_db_connection failed")
            return f"ERROR: Database connection check failed - {str(e)}"
