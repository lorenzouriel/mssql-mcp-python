"""
MCP Server bootstrap and transport selection.

Handles server initialization, transport selection (stdio vs HTTP),
and lifecycle management.
"""

import asyncio
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .config import settings, validate_settings
from .logging_config import setup_logging, get_logger
from .health import health_check, readiness_check, get_server_info, get_metrics_endpoint
from .tools import mcp as tools_mcp

logger = get_logger(__name__)


class MSSQLMCPServer:
    """Main MCP server class."""

    def __init__(self):
        self.mcp = None
        self.logger = get_logger(__name__)

    def setup(self) -> None:
        """Initialize server setup."""
        # Setup logging first
        setup_logging()

        self.logger.info("Starting MSSQL MCP Server v0.1.0")

        # Validate configuration
        is_valid, error = validate_settings()
        if not is_valid:
            self.logger.error("Configuration validation failed: %s", error)
            raise ValueError(error)

        self.logger.info("Configuration validated successfully")
        self.logger.info("Mode: %s", "read-only" if settings.READ_ONLY else "write-enabled")
        self.logger.info("Transport: %s", settings.MCP_TRANSPORT)

    async def run(self) -> None:
        """
        Run the server.

        Selects transport (stdio or HTTP) and starts the server.
        """
        self.setup()

        if settings.MCP_TRANSPORT == "stdio":
            await self._run_stdio()
        elif settings.MCP_TRANSPORT == "http":
            await self._run_http()
        else:
            raise ValueError(f"Unknown transport: {settings.MCP_TRANSPORT}")

    async def _run_stdio(self) -> None:
        """Run server with stdio transport."""
        self.logger.info("Starting MCP server with stdio transport")

        # The tools_mcp from tools.py is a FastMCP instance
        # It handles stdio transport automatically
        import sys
        from mcp.server.stdio import stdio_server

        # Create transport handler
        async with stdio_server(tools_mcp.server) as streams:
            await tools_mcp.server.run(
                sys.stdin.buffer,
                sys.stdout.buffer,
            )

    async def _run_http(self) -> None:
        """Run server with HTTP transport."""
        self.logger.info(
            "Starting MCP server with HTTP transport on %s:%d",
            settings.HTTP_BIND_HOST,
            settings.HTTP_BIND_PORT,
        )

        try:
            from fastapi import FastAPI
            from fastapi.responses import Response, JSONResponse
            import uvicorn

            app = FastAPI(
                title="MSSQL MCP Server",
                version="0.1.0",
                description="MCP server for SQL Server database access",
            )

            # Register health endpoints
            @app.get("/health")
            async def health():
                """Liveness probe."""
                result = await health_check()
                return JSONResponse(result)

            @app.get("/ready")
            async def ready():
                """Readiness probe."""
                result = await readiness_check()
                status_code = 200 if result["status"] == "ready" else 503
                return JSONResponse(result, status_code=status_code)

            @app.get("/info")
            async def info():
                """Server information."""
                result = await get_server_info()
                return JSONResponse(result)

            @app.get("/metrics")
            async def metrics():
                """Prometheus metrics."""
                metrics_text = await get_metrics_endpoint()
                return Response(metrics_text, media_type="text/plain")

            # MCP-specific endpoints (if using HTTP transport)
            @app.post("/mcp/invoke")
            async def invoke_mcp(request: dict):
                """Invoke MCP tool (HTTP transport)."""
                tool_name = request.get("tool")
                arguments = request.get("arguments", {})

                # This would delegate to tools_mcp
                try:
                    # Placeholder - actual implementation depends on FastMCP HTTP support
                    return JSONResponse({"error": "HTTP transport tool invocation not yet implemented"}, status_code=501)
                except Exception as e:
                    return JSONResponse({"error": str(e)}, status_code=500)

            # Run Uvicorn server
            config = uvicorn.Config(
                app=app,
                host=settings.HTTP_BIND_HOST,
                port=settings.HTTP_BIND_PORT,
                log_level=settings.LOG_LEVEL.lower(),
            )
            server = uvicorn.Server(config)
            await server.serve()

        except ImportError:
            self.logger.error("FastAPI and uvicorn required for HTTP transport")
            raise


def create_server() -> MSSQLMCPServer:
    """
    Factory function to create and configure the MCP server.

    Returns:
        Configured MSSQLMCPServer instance
    """
    return MSSQLMCPServer()


async def main() -> None:
    """Main entry point."""
    server = create_server()
    try:
        await server.run()
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.exception("Server error: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
