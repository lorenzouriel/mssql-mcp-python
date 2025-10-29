"""
Database layer for MSSQL MCP Server.

Provides connection pooling, query execution with timeouts, and safe result handling.
Uses pyodbc with connection pooling and thread-safe execution via asyncio.to_thread.
"""

import asyncio
import logging
from contextlib import contextmanager
from typing import List, Tuple, Iterator, Optional, Any
import pyodbc

from .config import settings

logger = logging.getLogger(__name__)

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


@contextmanager
def get_connection():
    """
    Context manager for database connections with automatic cleanup.
    Uses connection pooling for efficiency.
    """
    conn = None
    try:
        conn = pyodbc.connect(
            settings.MSSQL_CONNECTION_STRING,
            autocommit=False,
            timeout=settings.MSSQL_CONNECTION_TIMEOUT,
        )
        # Set connection options
        conn.setencoding(encoding="utf-8")
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
) -> Tuple[List[str], List[Tuple[Any, ...]]]:
    """
    Execute a SQL SELECT statement asynchronously.

    Runs in a thread to avoid blocking the event loop. Returns columns and rows.

    Args:
        sql: SQL query string (should be SELECT)
        params: Query parameters (for parameterized queries)
        timeout: Query timeout in seconds (defaults to MSSQL_QUERY_TIMEOUT)
        max_rows: Maximum rows to return (defaults to MAX_ROWS_PER_QUERY)

    Returns:
        Tuple of (column_names, rows)

    Raises:
        QueryTimeoutError: If query exceeds timeout
        DatabaseError: For other database errors
    """
    if timeout is None:
        timeout = settings.MSSQL_QUERY_TIMEOUT
    if max_rows is None:
        max_rows = settings.MAX_ROWS_PER_QUERY

    def _sync_execute() -> Tuple[List[str], List[Tuple[Any, ...]]]:
        """Synchronous query execution in thread."""
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                # Extract column names from cursor description
                columns = [desc[0] for desc in cursor.description] if cursor.description else []

                # Fetch rows with batch processing for memory efficiency
                rows: List[Tuple[Any, ...]] = []
                if columns:
                    batch_size = 1000
                    while True:
                        batch = cursor.fetchmany(batch_size)
                        if not batch:
                            break
                        rows.extend(batch)
                        if len(rows) >= max_rows:
                            rows = rows[:max_rows]
                            break
                else:
                    # No columns means no result set (USE statement)
                    conn.commit()

                return columns, rows
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


async def execute_schema_query(sql: str, timeout: Optional[int] = None) -> Tuple[List[str], List[Tuple[Any, ...]]]:
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
        cols, rows = await execute_schema_query(sql)
        if rows:
            return dict(zip(cols, rows[0]))
        return {}
    except Exception as e:
        logger.exception("Error fetching database info: %s", e)
        return {"error": str(e)}


async def check_connection() -> bool:
    """
    Test database connectivity.
    """
    try:
        cols, rows = await execute_query("SELECT 1 as test", timeout=5)
        return True
    except Exception as e:
        logger.error("Connection check failed: %s", e)
        return False
