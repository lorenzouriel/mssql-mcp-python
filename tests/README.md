# MSSQL MCP Server - Test Suite

Comprehensive test suite for the MSSQL MCP Server with unit and integration tests.

## Test Structure

```
tests/
├── unit/                      # Unit tests (fast, isolated)
│   ├── test_policy.py        # Policy engine tests
│   ├── test_config.py        # Configuration tests
│   ├── test_utils.py         # Utility function tests
│   └── test_db.py            # Database layer tests (mocked)
├── integration/               # Integration tests
│   ├── test_tools.py         # MCP tool integration tests
│   └── test_health.py        # Health endpoint tests
├── conftest.py               # Shared fixtures and configuration
└── __init__.py
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Only Unit Tests

```bash
pytest tests/unit/
# or
pytest -m unit
```

### Run Only Integration Tests

```bash
pytest tests/integration/
# or
pytest -m integration
```

### Run Specific Test File

```bash
pytest tests/unit/test_policy.py
```

### Run Specific Test

```bash
pytest tests/unit/test_policy.py::TestReadOnlyMode::test_allow_select_queries
```

### Run with Coverage

```bash
pytest --cov=src/mssql_mcp --cov-report=html --cov-report=term-missing
```

View coverage report:
```bash
# Open htmlcov/index.html in browser
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Debug Output

```bash
pytest -vv -s
```

## Test Categories

### Unit Tests (`tests/unit/`)

Fast, isolated tests that don't require external dependencies:

- **test_policy.py**: SQL validation, security policies, query mode detection
- **test_config.py**: Settings loading, validation, environment variables
- **test_utils.py**: Formatting, pagination, SQL escaping utilities
- **test_db.py**: Database connection and query execution (mocked)

### Integration Tests (`tests/integration/`)

Tests that verify component interaction:

- **test_tools.py**: MCP tool execution, policy + DB integration
- **test_health.py**: Health check endpoints, metrics, server info

## Test Markers

Tests are automatically marked based on location:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.asyncio` - Async tests
- `@pytest.mark.slow` - Slow running tests

## Configuration

### pytest.ini

Main pytest configuration with test discovery, markers, and output options.

### conftest.py

Shared fixtures:
- `test_config` - Test configuration
- `mock_settings` - Mock settings instance
- `sample_query_results` - Sample DB results
- `sample_sql_queries` - Sample SQL queries
- `mock_db_connection` - Mock database connection

### .coveragerc

Coverage reporting configuration with source paths and exclusions.

## Writing Tests

### Unit Test Example

```python
import pytest
from mssql_mcp.policy import is_allowed_sql, QueryMode

def test_allow_select_query():
    """Test that SELECT queries are allowed."""
    allowed, reason = is_allowed_sql("SELECT * FROM users", QueryMode.READ_ONLY)
    assert allowed
    assert reason is None
```

### Async Integration Test Example

```python
import pytest
from mssql_mcp.tools import execute_sql

@pytest.mark.asyncio
async def test_execute_sql():
    """Test executing SQL via MCP tool."""
    result = await execute_sql("SELECT * FROM users")
    assert "users" in result or len(result) > 0
```

### Using Fixtures

```python
def test_with_sample_data(sample_query_results):
    """Test using sample data fixture."""
    headers, rows = sample_query_results
    assert len(headers) == 3
    assert len(rows) == 3
```

## Best Practices

1. **Keep unit tests fast** - Use mocks for external dependencies
2. **Test edge cases** - Empty inputs, nulls, errors
3. **Use descriptive names** - Test names should explain what they test
4. **One assertion per concept** - Tests should be focused
5. **Clean up resources** - Use fixtures for setup/teardown
6. **Test error handling** - Verify errors are handled gracefully

## Continuous Integration

Tests can be run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest --cov=src/mssql_mcp --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Troubleshooting

### Import Errors

If you get import errors, ensure you're running from the project root:

```bash
# From project root
python -m pytest
```

### Async Test Warnings

Async tests require `pytest-asyncio`:

```bash
pip install pytest-asyncio
```

### Coverage Not Working

Install coverage dependencies:

```bash
pip install pytest-cov
```

## Test Data

Test fixtures provide sample data:

- **Sample queries**: SELECT, INSERT, UPDATE, DELETE, DROP
- **Sample results**: User data with id, name, email
- **Mock settings**: Test configuration values

## Future Enhancements

- [ ] Add performance benchmarking tests
- [ ] Add end-to-end tests with real database
- [ ] Add property-based testing with Hypothesis
- [ ] Add mutation testing with mutmut
- [ ] Add load testing for concurrent queries
