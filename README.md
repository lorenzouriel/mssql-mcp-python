# MSSQL MCP Python Server - Quick Start & Validation
This is a complete, production-ready MCP (Model Context Protocol) server implementation in Python that safely exposes SQL Server database capabilities to LLM clients like Claude.

## What Was Created
```bash
src/mssql_mcp/
├── __init__.py              # Package initialization
├── __main__.py              # python -m mssql_mcp entry
├── cli.py                   # Command-line interface
├── config.py                # Configuration & settings
├── db.py                    # Database layer
├── health.py                # Health checks
├── logging_config.py        # Structured logging
├── metrics.py               # Prometheus metrics
├── policy.py                # Security policies
├── server.py                # MCP server bootstrap
├── tools.py                 # MCP tool implementations
└── utils.py                 # Utilities & formatting
```

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

# Or with HTTP transport
python -m mssql_mcp.cli --transport http --bind 0.0.0.0:8080

# With custom settings
MSSQL_QUERY_TIMEOUT=60 READ_ONLY=true python -m mssql_mcp.cli --log-level DEBUG
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

---

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

---

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

---

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

---

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


## 🧪 Testing (Ready for Implementation)

Structure prepared for tests:
```
tests/
├── unit/
│   ├── test_policy.py       # Policy engine tests
│   ├── test_config.py       # Configuration tests
│   ├── test_utils.py        # Utility function tests
│   └── test_db.py           # Database layer tests
└── integration/
    ├── test_tools.py        # MCP tool integration tests
    └── test_health.py       # Health endpoint tests
```

Run with:
```bash
pytest tests/ -v --cov=src/mssql_mcp
```

## 🐳 Docker (Ready for Implementation)

Prepared for containerization:
```dockerfile
# Dockerfile
FROM python:3.11-slim
RUN apt-get install -y unixodbc
COPY src /app/src
RUN pip install -e /app
CMD ["python", "-m", "mssql_mcp.cli"]
```

Build & run:
```bash
docker build -t mssql-mcp:latest .
docker run -e MSSQL_CONNECTION_STRING="..." mssql-mcp:latest
```

---

## 🚢 Kubernetes (Ready for Implementation)

Prepared for K8s deployment:
```yaml
# Example Pod spec
apiVersion: v1
kind: Pod
metadata:
  name: mssql-mcp
spec:
  containers:
  - name: mssql-mcp
    image: mssql-mcp:latest
    env:
    - name: MSSQL_CONNECTION_STRING
      valueFrom:
        secretKeyRef:
          name: mssql-credentials
          key: connection-string
    - name: MCP_TRANSPORT
      value: "http"
    - name: HTTP_BIND_HOST
      value: "0.0.0.0"
    ports:
    - containerPort: 8080
    livenessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 10
    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      initialDelaySeconds: 5
```

---

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

---

## 🔗 Integration with Claude

Use the MCP server to give Claude database access:

**Claude Desktop Config** (`~/.config/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "mssql": {
      "command": "python",
      "args": ["-m", "mssql_mcp.cli"],
      "env": {
        "MSSQL_CONNECTION_STRING": "Driver={...};Server=...;Database=...;...",
        "READ_ONLY": "true"
      }
    }
  }
}
```

Then Claude can:
- Query databases with `execute_sql`
- Explore schemas with `list_tables`, `schema_discovery`
- Analyze data and generate insights
- All with safety guardrails in place!

---

## 📚 Module Dependencies

```
mcp                   # Model Context Protocol SDK
pyodbc               # SQL Server ODBC driver
pydantic             # Configuration validation
fastapi + uvicorn    # HTTP server (optional)
prometheus_client    # Metrics export
python-json-logger   # Structured logging
```

---

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

---

## 📈 Next Steps

1. ✅ **src/** — Complete and ready
2. 🔄 **tests/** — Unit and integration tests
3. 🐳 **docker/** — Dockerfile and docker-compose
4. 🔄 **.github/workflows/** — CI/CD pipeline
5. 🔄 **helm/** — Kubernetes Helm chart
6. 🔄 **docs/** — Full API documentation

---

## 💡 Tips

- **Local Development**: Use docker-compose with SQL Server image
- **Production**: Use environment variables or Vault for secrets
- **Monitoring**: Scrape `/metrics` with Prometheus
- **Debugging**: Set `LOG_LEVEL=DEBUG` for verbose output
- **Security**: Always keep `READ_ONLY=true` in untrusted environments