"""
Unit tests for policy engine.

Tests SQL validation, security policies, and audit logging.
"""

import pytest
from mssql_mcp.policy import (
    is_allowed_sql,
    QueryMode,
    hash_sql,
    normalize_sql,
    get_query_mode,
    validate_with_audit,
    explain_policy,
)
from mssql_mcp.config import settings


class TestSQLNormalization:
    """Test SQL normalization functions."""

    def test_normalize_sql(self):
        """Test SQL normalization."""
        assert normalize_sql("SELECT * FROM users") == "SELECT * FROM USERS"
        assert normalize_sql("  SELECT   *   FROM   users  ") == "SELECT * FROM USERS"
        assert normalize_sql("select\n*\nfrom\nusers") == "SELECT * FROM USERS"

    def test_hash_sql(self):
        """Test SQL hashing for safe logging."""
        sql1 = "SELECT * FROM users WHERE id = 1"
        sql2 = "SELECT * FROM users WHERE id = 2"

        hash1 = hash_sql(sql1)
        hash2 = hash_sql(sql2)

        # Same SQL should produce same hash
        assert hash_sql(sql1) == hash1
        # Different SQL should produce different hash
        assert hash1 != hash2
        # Hash should be 16 chars
        assert len(hash1) == 16


class TestReadOnlyMode:
    """Test read-only mode SQL validation."""

    def test_allow_select_queries(self):
        """SELECT queries should be allowed in read-only mode."""
        queries = [
            "SELECT * FROM users",
            "SELECT id, name FROM products WHERE price > 100",
            "SELECT COUNT(*) FROM orders",
        ]
        for query in queries:
            allowed, reason = is_allowed_sql(query, QueryMode.READ_ONLY)
            assert allowed, f"Query should be allowed: {query}, reason: {reason}"

    def test_block_write_queries(self):
        """Write queries should be blocked in read-only mode."""
        queries = [
            "INSERT INTO users (name) VALUES ('test')",
            "UPDATE users SET name = 'new'",
            "DELETE FROM users",
            "DROP TABLE users",
            "TRUNCATE TABLE users",
            "ALTER TABLE users ADD COLUMN email VARCHAR(255)",
            "CREATE TABLE test (id INT)",
        ]
        for query in queries:
            allowed, reason = is_allowed_sql(query, QueryMode.READ_ONLY)
            assert not allowed, f"Query should be blocked: {query}"
            assert reason is not None

    def test_block_exec_statements(self):
        """EXEC/EXECUTE should be blocked in read-only mode."""
        queries = [
            "EXEC sp_help",
            "EXECUTE sp_executesql N'SELECT * FROM users'",
        ]
        for query in queries:
            allowed, reason = is_allowed_sql(query, QueryMode.READ_ONLY)
            assert not allowed, f"Query should be blocked: {query}"


class TestAlwaysBannedPatterns:
    """Test always-banned patterns regardless of mode."""

    def test_block_extended_procedures(self):
        """Extended procedures should always be blocked."""
        queries = [
            "EXEC xp_cmdshell 'dir'",
            "SELECT * FROM users; EXEC xp_regread",
        ]
        for query in queries:
            allowed, reason = is_allowed_sql(query, QueryMode.READ_ONLY)
            assert not allowed, f"Query should be blocked: {query}"

    def test_block_dangerous_commands(self):
        """Dangerous commands should always be blocked."""
        queries = [
            "KILL 123",
            "SHUTDOWN",
        ]
        for query in queries:
            allowed, reason = is_allowed_sql(query, QueryMode.READ_ONLY)
            assert not allowed, f"Query should be blocked: {query}"


class TestQueryValidation:
    """Test general query validation."""

    def test_empty_query(self):
        """Empty queries should be rejected."""
        allowed, reason = is_allowed_sql("")
        assert not allowed
        assert "Empty SQL query" in reason

    def test_query_length_limit(self):
        """Queries exceeding max length should be rejected."""
        max_len = settings.MAX_QUERY_LENGTH
        long_query = "SELECT " + "a" * (max_len + 1)

        allowed, reason = is_allowed_sql(long_query)
        assert not allowed
        assert "exceeds maximum length" in reason

    def test_multi_statement_queries(self):
        """Multi-statement queries should be blocked."""
        query = "SELECT * FROM users; SELECT * FROM products"
        allowed, reason = is_allowed_sql(query)
        assert not allowed
        assert "Multi-statement" in reason

    def test_single_statement_with_trailing_semicolon(self):
        """Single statement with trailing semicolon should be allowed."""
        query = "SELECT * FROM users;"
        allowed, reason = is_allowed_sql(query, QueryMode.READ_ONLY)
        assert allowed


class TestQueryMode:
    """Test query mode determination."""

    def test_get_query_mode_read_only(self):
        """Test read-only mode detection."""
        original = settings.READ_ONLY
        settings.READ_ONLY = True

        mode = get_query_mode()
        assert mode == QueryMode.READ_ONLY

        settings.READ_ONLY = original

    def test_get_query_mode_write(self):
        """Test write mode detection."""
        original_ro = settings.READ_ONLY
        original_ew = settings.ENABLE_WRITES

        settings.READ_ONLY = False
        settings.ENABLE_WRITES = True

        mode = get_query_mode()
        assert mode == QueryMode.WRITE

        settings.READ_ONLY = original_ro
        settings.ENABLE_WRITES = original_ew


class TestAuditValidation:
    """Test validation with audit logging."""

    def test_validate_with_audit_allowed(self):
        """Test audit logging for allowed queries."""
        query = "SELECT * FROM users"
        allowed, reason = validate_with_audit(
            query, client_id="test_client", tool_name="execute_sql"
        )
        assert allowed
        assert reason is None

    def test_validate_with_audit_denied(self):
        """Test audit logging for denied queries."""
        query = "DROP TABLE users"
        allowed, reason = validate_with_audit(
            query, client_id="test_client", tool_name="execute_sql"
        )
        assert not allowed
        assert reason is not None


class TestPolicyExplanation:
    """Test policy explanation."""

    def test_explain_policy(self):
        """Test policy explanation returns expected structure."""
        policy = explain_policy()

        assert "query_mode" in policy
        assert "read_only" in policy
        assert "max_rows_per_query" in policy
        assert "allowed_tools" in policy
        assert isinstance(policy["allowed_tools"], list)
