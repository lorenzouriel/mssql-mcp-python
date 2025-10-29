"""
Entrypoint for running the MSSQL MCP server via: python -m mssql_mcp
"""

from .cli import run

if __name__ == "__main__":
    run()
