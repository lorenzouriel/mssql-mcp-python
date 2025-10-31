# Testing Guide - MSSQL MCP Server

Quick reference for running tests on the MSSQL MCP Server.

## Quick Start

```bash
# Install dependencies (if not already installed)
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=src/mssql_mcp --cov-report=html
```

## Test Organization

| Directory | Type | Description |
|-----------|------|-------------|
| `tests/unit/` | Unit | Fast, isolated tests with mocked dependencies |
| `tests/integration/` | Integration | Component interaction tests |

## Common Commands

### Run Specific Test Types

```bash
# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Tests marked as 'unit'
pytest -m unit

# Tests marked as 'integration'
pytest -m integration
```

### Run Specific Files or Tests

```bash
# Single file
pytest tests/unit/test_policy.py

# Single test class
pytest tests/unit/test_policy.py::TestReadOnlyMode

# Single test method
pytest tests/unit/test_policy.py::TestReadOnlyMode::test_allow_select_queries
```

### Debugging Tests

```bash
# Verbose output
pytest -vv

# Show print statements
pytest -s

# Stop at first failure
pytest -x

# Show local variables in traceback
pytest -l

# Run last failed tests
pytest --lf

# Debug with pdb on failure
pytest --pdb
```

### Coverage Reports

```bash
# Terminal coverage report
pytest --cov=src/mssql_mcp --cov-report=term-missing

# HTML coverage report (open htmlcov/index.html)
pytest --cov=src/mssql_mcp --cov-report=html

# XML coverage (for CI/CD)
pytest --cov=src/mssql_mcp --cov-report=xml

# All report formats
pytest --cov=src/mssql_mcp --cov-report=html --cov-report=term-missing --cov-report=xml
```

## Test Files Overview

### Unit Tests

| File | Tests | Lines |
|------|-------|-------|
| `test_policy.py` | SQL validation, security policies | ~180 |
| `test_config.py` | Configuration, settings validation | ~180 |
| `test_utils.py` | Formatting, pagination, escaping | ~240 |
| `test_db.py` | Database connections (mocked) | ~180 |

### Integration Tests

| File | Tests | Lines |
|------|-------|-------|
| `test_tools.py` | MCP tool execution flow | ~220 |
| `test_health.py` | Health/readiness endpoints | ~280 |

## Expected Test Results

All tests should pass on a fresh installation:

```
tests/unit/test_config.py ............... PASSED
tests/unit/test_db.py ................... PASSED
tests/unit/test_policy.py ............... PASSED
tests/unit/test_utils.py ................ PASSED
tests/integration/test_tools.py ......... PASSED
tests/integration/test_health.py ........ PASSED

======================== XX passed in X.XXs =========================
```

## Troubleshooting

### Import Errors

```bash
# Ensure you're in project root
cd /path/to/mssql-mcp-python

# Run with python module
python -m pytest
```

### Async Test Errors

```bash
# Install pytest-asyncio
pip install pytest-asyncio
```

### Coverage Missing

```bash
# Install coverage tools
pip install pytest-cov
```

### Mock Errors

```bash
# Ensure you have unittest.mock (Python 3.3+)
python --version  # Should be 3.8+
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run tests
        run: |
          pytest --cov=src/mssql_mcp --cov-report=xml --cov-report=term-missing

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## Writing New Tests

### Unit Test Template

```python
import pytest
from mssql_mcp.module import function_to_test

class TestFeature:
    """Test suite for feature."""

    def test_basic_case(self):
        """Test basic functionality."""
        result = function_to_test("input")
        assert result == "expected"

    def test_edge_case(self):
        """Test edge case handling."""
        result = function_to_test("")
        assert result is None
```

### Integration Test Template

```python
import pytest
from unittest.mock import patch

class TestIntegration:
    """Integration test suite."""

    @pytest.mark.asyncio
    @patch('mssql_mcp.module.dependency')
    async def test_async_flow(self, mock_dep):
        """Test async integration flow."""
        mock_dep.return_value = "mocked"
        result = await async_function()
        assert "expected" in result
```

## Test Fixtures

Available in `conftest.py`:

- `test_config` - Test configuration dict
- `mock_settings` - Mock Settings instance
- `sample_query_results` - Sample DB results (headers, rows)
- `sample_sql_queries` - Sample SQL queries dict
- `mock_db_connection` - Mock database connection
- `capture_logs` - Capture log messages

## Coverage Goals

Target coverage levels:

- **Overall**: > 80%
- **Critical modules** (policy, config): > 90%
- **Utilities**: > 85%
- **Integration**: > 70%

## Performance Benchmarks

Expected test execution times:

- Unit tests: < 2 seconds
- Integration tests: < 5 seconds
- Full suite: < 10 seconds

## Additional Resources

- [Detailed Test Documentation](tests/README.md)
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)

## Support

For issues with tests:
1. Check test output for specific failures
2. Review test documentation in `tests/README.md`
3. Verify dependencies are installed
4. Check Python version compatibility (3.8+)
