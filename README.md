# MSSQL MCP Python Server
This is a complete, production-ready MCP (Model Context Protocol) server implementation in Python that safely exposes SQL Server database capabilities to LLM clients like Claude.

## Quick Start
### 1. Install Dependencies
```bash
cd mssql-mcp-python
pip install -r requirements.txt

# or for development:
pip install -e ".[dev]"
```

### 2. Configure Database

Create `.env` file:
```bash
# For local SQL Server (Linux/Docker)
export MSSQL_CONNECTION_STRING="Driver={ODBC Driver 17 for SQL Server};Server=localhost,1433;Database=master;UID=sa;PWD=YourPassword123"

# Or for Windows Auth
export MSSQL_CONNECTION_STRING="Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=master;Trusted_Connection=yes"
```

### 3. Run the Server
```bash
# With stdio transport (for MCP clients)
python -m mssql_mcp.cli

# With custom settings
MSSQL_QUERY_TIMEOUT=60 READ_ONLY=true python -m mssql_mcp.cli --log-level DEBUG

# Or with HTTP transport
python -m mssql_mcp.cli --transport http --bind 0.0.0.0:8080

# Build and run
docker build -t mssql-mcp:latest .
docker run -e MSSQL_CONNECTION_STRING="..." mssql-mcp:latest
```

### 4. Test with curl (HTTP mode)
```bash
# Health check
curl http://localhost:8080/health

# Readiness check
curl http://localhost:8080/ready

# Server info
curl http://localhost:8080/info

# Prometheus metrics
curl http://localhost:8080/metrics
```

## 🔧 Configuration Reference
All settings can be set via environment variables or `.env` file:
| Setting | Default | Description |
|---------|---------|-------------|
| `MSSQL_CONNECTION_STRING` | — | **Required** database connection string |
| `MSSQL_CONNECTION_TIMEOUT` | 5s | Connection establishment timeout |
| `MSSQL_QUERY_TIMEOUT` | 30s | Query execution timeout |
| `MSSQL_MAX_POOL_SIZE` | 10 | Connection pool size |
| `READ_ONLY` | `true` | Enforce read-only mode |
| `ENABLE_WRITES` | `false` | Allow write/DDL operations |
| `MAX_ROWS_PER_QUERY` | 50,000 | Maximum rows to return |
| `MAX_QUERY_LENGTH` | 50,000 | Maximum query size (chars) |
| `MCP_TRANSPORT` | `stdio` | Transport: `stdio` or `http` |
| `HTTP_BIND_HOST` | `127.0.0.1` | HTTP bind address |
| `HTTP_BIND_PORT` | 8080 | HTTP port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `json` | Log format: `json` or `text` |
| `ENABLE_METRICS` | `true` | Enable Prometheus metrics |
| `ENABLE_HEALTH_CHECKS` | `true` | Enable health endpoints |
| `SENTRY_DSN` | — | Optional Sentry error tracking |

## 📋 Available MCP Tools
The server exposes these tools to MCP clients:

### 1. `execute_sql(sql, format="table")`
Execute SELECT queries (or write operations if enabled)
```
Input: "SELECT * FROM users LIMIT 10"
Output: ASCII table or JSON
```

### 2. `list_schemas()`
List all database schemas
```
Input: (none)
Output: Schema names list
```

### 3. `list_tables(schema, limit=200)`
List tables with optional schema filter
```
Input: schema="dbo", limit=100
Output: Table list with metadata
```

### 4. `schema_discovery(schema)`
Get full schema metadata (tables, columns, types)
```
Input: schema="dbo"
Output: JSON with detailed column info
```

### 5. `get_database_info()`
Get server/database metadata
```
Input: (none)
Output: Database name, version, machine name
```

### 6. `get_policy_info()`
Get current security policy settings
```
Input: (none)
Output: Policy details (allowed operations, limits)
```

### 7. `check_db_connection()`
Health check for database connectivity
```
Input: (none)
Output: Connection status
```

## 🔐 Security Features
✅ **Read-Only by Default**
- Only SELECT queries allowed unless explicitly enabled
- Writes require `ENABLE_WRITES=true` + `ADMIN_CONFIRM` token

✅ **SQL Injection Prevention**
- Parameterized queries via pyodbc
- Multi-statement query blocking
- Banned keyword detection (DROP, ALTER, EXEC, etc.)

✅ **Sensitive Data Protection**
- Automatic log redaction (passwords, connection strings)
- Query hashing for safe logging
- No credentials in response bodies

✅ **Resource Limits**
- Query timeouts (default 30s)
- Row limits (default 50,000 rows)
- Query length limits (50KB)
- Connection pool limits

✅ **Audit Trail**
- Structured logging with request metadata
- Query metrics and statistics
- Client ID tracking (when provided)

## 📊 Observability
### Prometheus Metrics
Available at `GET /metrics` (HTTP mode):
- `mssql_queries_executed_total` — Total queries by tool and status
- `mssql_queries_blocked_total` — Blocked queries by reason
- `mssql_query_duration_seconds` — Query latency histogram
- `mssql_query_rows_returned` — Result set size histogram
- `mssql_active_queries` — Currently executing queries
- `mssql_server_ready` — Server readiness (0/1)

### Structured Logs
All logs in JSON format (when `LOG_FORMAT=json`):
```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "level": "INFO",
  "logger": "mssql_mcp.tools",
  "message": "Query allowed",
  "module": "tools",
  "function": "execute_sql",
  "line": 42
}
```

### Health Checks
- `GET /health` — Liveness probe (always 200)
- `GET /ready` — Readiness probe (200 if DB connected)


## 🧪 Testing
Comprehensive test suite with unit and integration tests:
```bash
tests/
├── unit/
│   ├── test_policy.py       # Policy engine tests
│   ├── test_config.py       # Configuration tests
│   ├── test_utils.py        # Utility function tests
│   └── test_db.py           # Database layer tests (mocked)
├── integration/
│   ├── test_tools.py        # MCP tool integration tests
│   └── test_health.py       # Health endpoint tests
├── conftest.py              # Shared fixtures and configuration
└── README.md                # Detailed test documentation
```

### Run Tests
```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run with coverage report
pytest --cov=src/mssql_mcp --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_policy.py -v

# Run specific test
pytest tests/unit/test_policy.py::TestReadOnlyMode::test_allow_select_queries
```

### Test Coverage
- **Policy Engine**: SQL validation, security policies, query mode detection
- **Configuration**: Settings loading, validation, environment variables
- **Utilities**: Formatting (table/JSON/CSV), pagination, SQL escaping
- **Database Layer**: Connection handling, query execution, error handling
- **MCP Tools**: Tool execution, policy integration, result formatting
- **Health Endpoints**: Liveness, readiness, metrics, server info

See [tests/README.md](tests/README.md) for detailed documentation.

## 📝 Code Quality
The codebase includes:
✅ **Type Hints** — Full type annotations for mypy
✅ **Docstrings** — Comprehensive module and function documentation
✅ **Error Handling** — Custom exceptions and graceful error recovery
✅ **Logging** — Structured logging at appropriate levels
✅ **Validation** — Input validation and policy checks
✅ **Security** — Built-in security best practices
✅ **Metrics** — Observable performance and health
✅ **Configuration** — Flexible, environment-driven setup

## 🔗 Integration with Claude
Use the MCP server to give Claude database access:
- **Windows** (`%APPDATA%\Claude\claude_desktop_config.json`):
- **macOS**: (`~/Library/Application Support/Claude/claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "mssql": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "MSSQL_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};Server=..;Database=fin_pulse;UID=mcp_readonly;PWD=mcp_readonly;TrustServerCertificate=yes;",
        "mssql-mcp:latest"
      ]
    }
  }
}
```

Then Claude can:
- Query databases with `execute_sql`
- Explore schemas with `list_tables`, `schema_discovery`
- Analyze data and generate insights
- All with safety guardrails in place!

## 🛠️ Common Tasks

### Change Log Level
```bash
LOG_LEVEL=DEBUG python -m mssql_mcp.cli
```

### Enable Write Operations
```bash
ENABLE_WRITES=true ADMIN_CONFIRM=secret python -m mssql_mcp.cli
```

### Increase Query Timeout
```bash
MSSQL_QUERY_TIMEOUT=120 python -m mssql_mcp.cli
```

### Run Multiple Instances
```bash
python -m mssql_mcp.cli --transport http --bind 127.0.0.1:8080
python -m mssql_mcp.cli --transport http --bind 127.0.0.1:8081  # Different port
```
