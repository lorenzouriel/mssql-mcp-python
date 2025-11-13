# Security Policy

## Supported Versions

We actively maintain and provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report security issues by emailing **[lorenzouriel394@gmail.com]** with:

- A description of the vulnerability
- Steps to reproduce the issue
- Potential impact of the vulnerability
- Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: We will acknowledge your email within 48 hours
- **Updates**: We will keep you informed of our progress
- **Timeline**: We aim to release a fix within 7-14 days for critical issues
- **Credit**: We will credit you in the release notes (unless you prefer to remain anonymous)

## Security Best Practices

When using MSSQL MCP Python, follow these security practices:

### 1. Connection Strings
- Never commit connection strings to version control
- Use environment variables or secure configuration management
- Restrict database user permissions to minimum required

### 2. Read-Only Mode
- Keep `READ_ONLY=true` (default) unless write operations are necessary
- Only enable writes with `ENABLE_WRITES=true` in controlled environments
- Use the `ADMIN_CONFIRM` token for write operations

### 3. Network Security
- Use firewall rules to restrict access to the MCP server
- Consider using VPN or private networks for database connections
- Enable TLS/SSL for SQL Server connections when possible

### 4. Query Limits
- Configure appropriate `MSSQL_QUERY_TIMEOUT` values
- Set `MAX_ROWS` to prevent excessive data retrieval
- Monitor query patterns for suspicious activity

### 5. Logging and Monitoring
- Enable structured logging with `LOG_FORMAT=json`
- Monitor logs for blocked queries and security events
- Set up alerts for unusual query patterns
- Use Prometheus metrics to track security-relevant events

### 6. Updates
- Keep dependencies up to date
- Regularly update to the latest version of MSSQL MCP Python
- Subscribe to security advisories for dependencies

## Known Security Features

✅ **SQL Injection Prevention**
- Parameterized queries via pyodbc
- Multi-statement query blocking
- Banned keyword detection

✅ **Sensitive Data Protection**
- Automatic log redaction for passwords and connection strings
- Query hashing for safe logging
- No credentials in response bodies

✅ **Resource Limits**
- Query timeouts (default 30s)
- Row limits (default 50,000 rows)
- Query length limits (50KB)

✅ **Audit Trail**
- Structured logging with request metadata
- Query metrics and statistics
- Client ID tracking

## Scope

This security policy applies to:
- The MSSQL MCP Python server code
- Official Docker images
- Documentation and examples

It does NOT cover:
- Third-party dependencies (report to their respective maintainers)
- User-deployed instances (your deployment security is your responsibility)
- SQL Server itself (report to Microsoft)

## Contact

For non-security issues, please use [GitHub Issues](https://github.com/lorenzouriel/mssql-mcp-python/issues).

For security concerns, email **[lorenzouriel394@gmail.com]**.
