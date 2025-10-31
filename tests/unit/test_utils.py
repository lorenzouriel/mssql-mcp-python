"""
Unit tests for utility functions.

Tests formatting, pagination, and SQL escaping utilities.
"""

import pytest
from mssql_mcp.utils import (
    format_table,
    format_json,
    format_csv,
    paginate_results,
    escape_sql_identifier,
    escape_sql_string,
    truncate_string,
    result_summary,
)
import json


class TestTableFormatting:
    """Test ASCII table formatting."""

    def test_format_empty_table(self):
        """Test formatting empty table."""
        result = format_table([], [])
        assert result == "(no columns)"

    def test_format_table_no_rows(self):
        """Test formatting table with headers but no rows."""
        headers = ["id", "name"]
        result = format_table(headers, [])
        assert result == "(no rows)"

    def test_format_simple_table(self):
        """Test formatting simple table."""
        headers = ["id", "name"]
        rows = [(1, "Alice"), (2, "Bob")]
        result = format_table(headers, rows)

        assert "id" in result
        assert "name" in result
        assert "Alice" in result
        assert "Bob" in result
        assert "|" in result  # Column separator
        assert "-" in result  # Divider

    def test_format_table_with_null(self):
        """Test formatting table with NULL values."""
        headers = ["id", "value"]
        rows = [(1, None), (2, "test")]
        result = format_table(headers, rows)

        assert "NULL" in result

    def test_format_table_with_bool(self):
        """Test formatting table with boolean values."""
        headers = ["id", "active"]
        rows = [(1, True), (2, False)]
        result = format_table(headers, rows)

        assert "true" in result
        assert "false" in result

    def test_format_table_with_binary(self):
        """Test formatting table with binary data."""
        headers = ["id", "data"]
        rows = [(1, b"binary"), (2, bytearray(b"bytes"))]
        result = format_table(headers, rows)

        assert "<binary>" in result


class TestJSONFormatting:
    """Test JSON formatting."""

    def test_format_json_empty(self):
        """Test formatting empty result set as JSON."""
        headers = ["id", "name"]
        rows = []
        result = format_json(headers, rows)

        parsed = json.loads(result)
        assert parsed == []

    def test_format_json_simple(self):
        """Test formatting simple result set as JSON."""
        headers = ["id", "name"]
        rows = [(1, "Alice"), (2, "Bob")]
        result = format_json(headers, rows)

        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0] == {"id": 1, "name": "Alice"}
        assert parsed[1] == {"id": 2, "name": "Bob"}

    def test_format_json_with_binary(self):
        """Test formatting JSON with binary data."""
        headers = ["id", "data"]
        rows = [(1, b"binary")]
        result = format_json(headers, rows)

        parsed = json.loads(result)
        assert parsed[0]["data"] == "<binary>"


class TestCSVFormatting:
    """Test CSV formatting."""

    def test_format_csv_simple(self):
        """Test formatting simple CSV."""
        headers = ["id", "name"]
        rows = [(1, "Alice"), (2, "Bob")]
        result = format_csv(headers, rows)

        lines = result.strip().split("\n")
        assert lines[0] == "id,name"
        assert "Alice" in lines[1]
        assert "Bob" in lines[2]

    def test_format_csv_with_null(self):
        """Test formatting CSV with NULL values."""
        headers = ["id", "value"]
        rows = [(1, None), (2, "test")]
        result = format_csv(headers, rows)

        lines = result.strip().split("\n")
        assert lines[1].startswith("1,")  # NULL becomes empty

    def test_format_csv_with_binary(self):
        """Test formatting CSV with binary data."""
        headers = ["id", "data"]
        rows = [(1, b"binary")]
        result = format_csv(headers, rows)

        assert "<binary>" in result


class TestPagination:
    """Test result pagination."""

    def test_paginate_first_page(self):
        """Test pagination for first page."""
        rows = [(i,) for i in range(250)]
        paginated, info = paginate_results(rows, page=1, per_page=100)

        assert len(paginated) == 100
        assert info["total_rows"] == 250
        assert info["page"] == 1
        assert info["total_pages"] == 3
        assert info["has_next"] is True
        assert info["has_prev"] is False

    def test_paginate_middle_page(self):
        """Test pagination for middle page."""
        rows = [(i,) for i in range(250)]
        paginated, info = paginate_results(rows, page=2, per_page=100)

        assert len(paginated) == 100
        assert info["page"] == 2
        assert info["has_next"] is True
        assert info["has_prev"] is True

    def test_paginate_last_page(self):
        """Test pagination for last page."""
        rows = [(i,) for i in range(250)]
        paginated, info = paginate_results(rows, page=3, per_page=100)

        assert len(paginated) == 50  # Remaining rows
        assert info["page"] == 3
        assert info["has_next"] is False
        assert info["has_prev"] is True

    def test_paginate_empty(self):
        """Test pagination with empty result set."""
        rows = []
        paginated, info = paginate_results(rows, page=1, per_page=100)

        assert len(paginated) == 0
        assert info["total_rows"] == 0
        assert info["total_pages"] == 0


class TestSQLEscaping:
    """Test SQL identifier and string escaping."""

    def test_escape_identifier_simple(self):
        """Test escaping simple identifier."""
        assert escape_sql_identifier("users") == "[users]"
        assert escape_sql_identifier("my_table") == "[my_table]"

    def test_escape_identifier_with_brackets(self):
        """Test escaping identifier with brackets."""
        assert escape_sql_identifier("table]name") == "[table]]name]"
        assert escape_sql_identifier("[users]") == "[[users]]]"

    def test_escape_identifier_empty(self):
        """Test escaping empty identifier."""
        assert escape_sql_identifier("") == "[]"

    def test_escape_string_simple(self):
        """Test escaping simple string."""
        assert escape_sql_string("hello") == "'hello'"
        assert escape_sql_string("world") == "'world'"

    def test_escape_string_with_quotes(self):
        """Test escaping string with quotes."""
        assert escape_sql_string("it's") == "'it''s'"
        assert escape_sql_string("O'Brien") == "'O''Brien'"

    def test_escape_string_empty(self):
        """Test escaping empty string."""
        assert escape_sql_string("") == "''"


class TestStringUtilities:
    """Test string utility functions."""

    def test_truncate_short_string(self):
        """Test truncating string shorter than max length."""
        result = truncate_string("hello", max_len=10)
        assert result == "hello"

    def test_truncate_long_string(self):
        """Test truncating long string."""
        long_str = "a" * 100
        result = truncate_string(long_str, max_len=20)

        assert len(result) == 20
        assert result.endswith("...")

    def test_truncate_custom_suffix(self):
        """Test truncating with custom suffix."""
        long_str = "a" * 100
        result = truncate_string(long_str, max_len=20, suffix=" [...]")

        assert len(result) == 20
        assert result.endswith(" [...]")

    def test_result_summary(self):
        """Test result set summary."""
        headers = ["id", "name", "email"]
        rows = [(1, "Alice", "a@ex.com"), (2, "Bob", "b@ex.com")]

        summary = result_summary(headers, rows)
        assert "2 row(s)" in summary
        assert "3 column(s)" in summary

    def test_result_summary_empty(self):
        """Test summary of empty result set."""
        headers = ["id", "name"]
        rows = []

        summary = result_summary(headers, rows)
        assert "0 row(s)" in summary
        assert "2 column(s)" in summary
