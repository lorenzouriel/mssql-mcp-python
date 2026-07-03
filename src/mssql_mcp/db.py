"""
Database layer for MSSQL MCP Server.

Provides connection pooling, query execution with timeouts, and safe result handling.
Uses pyodbc with connection pooling and thread-safe execution via asyncio.to_thread.
"""

import asyncio
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import List, Tuple, Iterator, Optional, Any
import pyodbc

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result of a query execution.

    Attributes:
        columns: Column names (empty for statements with no result set).
        rows: Result rows, capped at max_rows.
        truncated: True if more rows were available than max_rows.
        rowcount: Affected-row count for write statements; -1 when not applicable.
    """
    columns: List[str] = field(default_factory=list)
    rows: List[Tuple[Any, ...]] = field(default_factory=list)
    truncated: bool = False
    rowcount: int = -1

# Enable ODBC connection pooling for better resource management
pyodbc.pooling = True


class DatabaseError(Exception):
    """Base database error."""
    pass


class QueryTimeoutError(DatabaseError):
    """Query execution exceeded timeout."""
    pass


class ConnectionError(DatabaseError):
    """Database connection error."""
    pass


def _fetch_rows(cursor, max_rows: int, batch_size: int = 1000) -> Tuple[List[Tuple[Any, ...]], bool]:
    """Fetch up to max_rows rows from a cursor, reporting truncation.

    Allows the row count to exceed max_rows before trimming so that a result
    of exactly max_rows rows is not mislabelled as truncated.

    Returns (rows, truncated).
    """
    rows: List[Tuple[Any, ...]] = []
    truncated = False
    while True:
        batch = cursor.fetchmany(batch_size)
        if not batch:
            break
        rows.extend(batch)
        if len(rows) > max_rows:
            rows = rows[:max_rows]
            truncated = True
            break
    return rows, truncated


def _quote_odbc_value(value: str) -> str:
    """Wrap an ODBC connection value in braces if it contains special chars."""
    if value and (";" in value or "{" in value or "}" in value or value.strip() != value):
        return "{" + value.replace("}", "}}") + "}"
    return value


def build_connection_string() -> str:
    """Build the effective connection string, applying optional credential overrides.

    MSSQL_USER / MSSQL_PASSWORD (and MSSQL_TRUSTED_CONNECTION) take precedence over
    UID/PWD embedded in MSSQL_CONNECTION_STRING, so a deployment can run under its
    own SQL login without editing the base connection string. Only the credential
    keys being overridden are replaced; everything else is preserved.
    """
    base = settings.MSSQL_CONNECTION_STRING
    user = settings.MSSQL_USER
    password = settings.MSSQL_PASSWORD
    trusted = settings.MSSQL_TRUSTED_CONNECTION

    # No overrides configured -> use the connection string as-is.
    if not user and not password and trusted is None:
        return base

    # Determine which credential keys to drop from the base string.
    drop = set()
    if trusted is True:
        drop |= {"uid", "pwd", "user id", "password", "trusted_connection"}
    elif trusted is False:
        drop |= {"trusted_connection"}
    if user:
        drop |= {"uid", "user id"}
    if password:
        drop |= {"pwd", "password"}

    kept = []
    for part in base.split(";"):
        if not part.strip():
            continue
        key = part.split("=", 1)[0].strip().lower()
        if key in drop:
            continue
        kept.append(part.strip())

    if trusted is True:
        kept.append("Trusted_Connection=yes")
    else:
        if user:
            kept.append(f"UID={_quote_odbc_value(user)}")
        if password:
            kept.append(f"PWD={_quote_odbc_value(password)}")

    return ";".join(kept) + ";"


@contextmanager
def get_connection():
    """
    Context manager for database connections with automatic cleanup.
    Uses connection pooling for efficiency.
    """
    conn = None
    try:
        conn = pyodbc.connect(
            build_connection_string(),
            autocommit=False,
            timeout=settings.MSSQL_CONNECTION_TIMEOUT,
        )
        # Configure character encoding so non-ASCII data (e.g. accented text) is
        # sent and decoded correctly. SQL Server expects the query/parameter text
        # as UTF-16LE (setencoding); sending UTF-8 corrupts non-ASCII literals in
        # queries. Result decoding is set explicitly too, since pyodbc's platform
        # defaults can otherwise garble VARCHAR/NVARCHAR values.
        conn.setencoding(encoding=settings.MSSQL_WIDE_ENCODING)
        conn.setdecoding(pyodbc.SQL_CHAR, encoding=settings.MSSQL_ENCODING)
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding=settings.MSSQL_WIDE_ENCODING)
        conn.setdecoding(pyodbc.SQL_WMETADATA, encoding=settings.MSSQL_WIDE_ENCODING)
        yield conn
    except pyodbc.Error as e:
        logger.exception("Database connection error: %s", e)
        raise ConnectionError(f"Failed to connect to database: {e}") from e
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.warning("Error closing connection: %s", e)


async def execute_query(
    sql: str,
    params: Tuple = (),
    timeout: Optional[int] = None,
    max_rows: Optional[int] = None,
) -> QueryResult:
    """
    Execute a SQL statement asynchronously.

    Runs in a thread to avoid blocking the event loop. Handles both queries that
    return a result set (SELECT) and statements that do not (INSERT/UPDATE/DELETE).

    Args:
        sql: SQL statement to execute
        params: Query parameters (for parameterized queries)
        timeout: Query timeout in seconds (defaults to MSSQL_QUERY_TIMEOUT)
        max_rows: Maximum rows to return (defaults to MAX_ROWS_PER_QUERY)

    Returns:
        QueryResult with columns, rows, truncated flag and affected rowcount.

    Raises:
        QueryTimeoutError: If query exceeds timeout
        DatabaseError: For other database errors
    """
    if timeout is None:
        timeout = settings.MSSQL_QUERY_TIMEOUT
    if max_rows is None:
        max_rows = settings.MAX_ROWS_PER_QUERY

    def _sync_execute() -> QueryResult:
        """Synchronous query execution in thread."""
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                # Extract column names from cursor description
                columns = [desc[0] for desc in cursor.description] if cursor.description else []

                if columns:
                    # Fetch rows with batch processing for memory efficiency,
                    # flagging truncation when more than max_rows are available.
                    rows, truncated = _fetch_rows(cursor, max_rows)
                    return QueryResult(columns=columns, rows=rows, truncated=truncated)
                else:
                    # No result set: write statement (INSERT/UPDATE/DELETE) or USE.
                    # Capture affected rows and commit the transaction.
                    rowcount = cursor.rowcount
                    conn.commit()
                    return QueryResult(columns=[], rows=[], rowcount=rowcount)
            except pyodbc.Error as e:
                logger.exception("Query execution error: %s", e)
                raise DatabaseError(f"Query execution failed: {e}") from e
            finally:
                try:
                    cursor.close()
                except Exception as e:
                    logger.warning("Error closing cursor: %s", e)

    # Execute in thread with timeout
    try:
        coro = asyncio.to_thread(_sync_execute)
        result = await asyncio.wait_for(coro, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        logger.error("Query timeout after %d seconds", timeout)
        raise QueryTimeoutError(f"Query execution exceeded {timeout}s timeout") from None
    except Exception as e:
        if isinstance(e, (DatabaseError, QueryTimeoutError)):
            raise
        logger.exception("Unexpected error during query execution: %s", e)
        raise DatabaseError(f"Unexpected error: {e}") from e


async def execute_schema_query(sql: str, timeout: Optional[int] = None) -> QueryResult:
    """
    Execute a schema/metadata query with relaxed row limits.
    Used for list_tables, list_schemas, schema_discovery.
    """
    if timeout is None:
        timeout = settings.MSSQL_QUERY_TIMEOUT
    return await execute_query(sql, timeout=timeout, max_rows=10000)


async def get_database_info() -> dict:
    """
    Fetch general database information.
    """
    try:
        sql = """
        SELECT
            DB_NAME() as database_name,
            @@VERSION as version,
            SERVERPROPERTY('MachineName') as machine_name,
            SERVERPROPERTY('InstanceName') as instance_name
        """
        result = await execute_schema_query(sql)
        if result.rows:
            return dict(zip(result.columns, result.rows[0]))
        return {}
    except Exception as e:
        logger.exception("Error fetching database info: %s", e)
        return {"error": str(e)}


async def check_connection() -> bool:
    """
    Test database connectivity.
    """
    try:
        await execute_query("SELECT 1 as test", timeout=5)
        return True
    except Exception as e:
        logger.error("Connection check failed: %s", e)
        return False
