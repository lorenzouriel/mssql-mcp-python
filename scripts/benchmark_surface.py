#!/usr/bin/env python3
"""Measure the per-turn context footprint of the full vs lean tool surface.

The lean surface (`?mode=lean`) advertises only `execute_sql`, so an agent pays
for one tool schema instead of twelve on every turn. This script connects to a
running mssql-mcp server over streamable HTTP, pulls what each surface actually
advertises (the tool schemas + the server instructions the client puts in the
model context), and reports the footprint and the saving.

This measures the deterministic, always-present per-turn overhead — not a full
agent trajectory (that additionally depends on the model and the task). Token
counts use tiktoken (cl100k_base) when available as a portable proxy, otherwise a
transparent chars/4 estimate; the full-vs-lean delta is what matters and is
stable across tokenizers.

Usage:
    python scripts/benchmark_surface.py [BASE_MCP_URL]
    # BASE_MCP_URL default: http://localhost:8080/mcp
"""
import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _count_tokens(text: str):
    """Return (token_count, method). Prefer tiktoken; fall back to chars/4."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)), "tiktoken/cl100k_base"
    except Exception:
        return (len(text) + 3) // 4, "estimate chars/4"


async def _surface(base_url: str, mode: str):
    """Return (instructions, tools_payload) for one surface."""
    sep = "&" if "?" in base_url else "?"
    url = f"{base_url}{sep}mode={mode}"
    async with streamablehttp_client(url) as (r, w, _):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            instructions = init.instructions or ""
            tools = (await s.list_tools()).tools
            # What a client serialises into the model context per turn.
            payload = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema,
                }
                for t in tools
            ]
            return instructions, payload


async def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080/mcp"
    results = {}
    for mode in ("full", "lean"):
        instructions, payload = await _surface(base, mode)
        blob = instructions + "\n" + json.dumps(payload, ensure_ascii=False)
        tokens, method = _count_tokens(blob)
        results[mode] = {
            "tools": len(payload),
            "tool_names": [t["name"] for t in payload],
            "chars": len(blob),
            "tokens": tokens,
        }

    full, lean = results["full"], results["lean"]
    drop = (full["tokens"] - lean["tokens"]) / full["tokens"] * 100 if full["tokens"] else 0

    print(f"MCP endpoint: {base}")
    print(f"token method: {method}\n")
    print(f"{'surface':<8}{'tools':>7}{'chars':>10}{'tokens':>10}")
    print("-" * 35)
    for name in ("full", "lean"):
        r = results[name]
        print(f"{name:<8}{r['tools']:>7}{r['chars']:>10}{r['tokens']:>10}")
    print("-" * 35)
    print(f"lean tool-surface footprint: -{drop:.0f}% tokens "
          f"({full['tokens']} -> {lean['tokens']})")
    print(f"lean advertises: {lean['tool_names']}")


if __name__ == "__main__":
    asyncio.run(main())
