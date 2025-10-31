"""
Pytest configuration and fixtures.

Provides shared fixtures and configuration for all tests.
"""

import pytest
import sys
import os
from pathlib import Path

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration."""
    return {
        "test_mode": True,
        "mock_db": True,
    }


@pytest.fixture(scope="function")
def mock_settings():
    """Provide mock settings for tests."""
    from mssql_mcp.config import Settings

    return Settings(
        MSSQL_CONNECTION_STRING="Driver={test};Server=test",
        READ_ONLY=True,
        ENABLE_WRITES=False,
        MAX_ROWS_PER_QUERY=1000,
        MAX_QUERY_LENGTH=10000,
    )


@pytest.fixture(scope="function")
def sample_query_results():
    """Provide sample query results for testing."""
    headers = ["id", "name", "email"]
    rows = [
        (1, "Alice Johnson", "alice@example.com"),
        (2, "Bob Smith", "bob@example.com"),
        (3, "Carol White", "carol@example.com"),
    ]
    return headers, rows


@pytest.fixture(scope="function")
def sample_sql_queries():
    """Provide sample SQL queries for testing."""
    return {
        "select": "SELECT * FROM users WHERE id = 1",
        "insert": "INSERT INTO users (name) VALUES ('test')",
        "update": "UPDATE users SET name = 'new' WHERE id = 1",
        "delete": "DELETE FROM users WHERE id = 1",
        "drop": "DROP TABLE users",
        "multi": "SELECT * FROM users; SELECT * FROM products",
    }


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset settings before each test."""
    # This fixture runs automatically before each test
    # Add any cleanup or reset logic here if needed
    yield
    # Cleanup after test
    pass


@pytest.fixture(scope="function")
async def mock_db_connection():
    """Provide mock database connection."""
    from unittest.mock import Mock, AsyncMock

    conn = Mock()
    conn.cursor = Mock()
    conn.commit = Mock()
    conn.rollback = Mock()
    conn.close = Mock()

    return conn


@pytest.fixture(scope="function")
def capture_logs(caplog):
    """Fixture to capture log messages."""
    import logging

    caplog.set_level(logging.INFO)
    return caplog


# Markers for categorizing tests
def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


# Hook to add markers automatically based on test location
def pytest_collection_modifyitems(config, items):
    """Automatically add markers based on test location."""
    for item in items:
        # Add 'unit' marker to tests in tests/unit/
        if "tests/unit" in str(item.fspath) or "tests\\unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Add 'integration' marker to tests in tests/integration/
        if "tests/integration" in str(item.fspath) or "tests\\integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Add 'asyncio' marker to async test functions
        if item.get_closest_marker("asyncio"):
            item.add_marker(pytest.mark.asyncio)
