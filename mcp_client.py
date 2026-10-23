"""Minimal synchronous MCP client over Streamable HTTP.

Uses the official ``mcp`` SDK client: performs the real initialize
handshake, negotiates the protocol version, and calls tools. The
simulated Alexa+ front end and the test-suite both go through this module,
so the demo path exercises the genuine protocol — no shortcuts, no
in-process calls.

Session-per-call by design: the *memory* is the stateful part (it lives in
the server's graph store); client sessions are cheap and disposable.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import httpx

from mcp import ClientSession

try:  # SDK >= 1.28: new name AND new signature (takes a built client)
    from mcp.client.streamable_http import streamable_http_client as _http_client_fn
    _NEW_API = True
except ImportError:  # pragma: no cover - older SDKs
    from mcp.client.streamable_http import streamablehttp_client as _http_client_fn
    _NEW_API = False


def _client_kwargs() -> dict:
    """httpx settings for talking to a (usually local) MCP server.

    trust_env=False is load-bearing: ambient HTTP_PROXY/NO_PROXY variables
    must not reroute or break loopback traffic. (Observed in the wild: a
    bracketed IPv6 entry in NO_PROXY made httpx raise InvalidURL for a
    127.0.0.1 server.)
    """
    return {
        "trust_env": False,
        "follow_redirects": True,
        "timeout": httpx.Timeout(30.0, read=300.0),
    }


@asynccontextmanager
async def _connect(url: str):
    if _NEW_API:
        async with httpx.AsyncClient(**_client_kwargs()) as hc:
            async with _http_client_fn(url, http_client=hc) as streams:
                yield streams
    else:  # pragma: no cover
        def factory(headers=None, timeout=None, auth=None):
            return httpx.AsyncClient(headers=headers, auth=auth,
                                     **_client_kwargs())
        async with _http_client_fn(url, httpx_client_factory=factory) as streams:
            yield streams


async def _call(url: str, tool: str, arguments: dict) -> dict:
    async with _connect(url) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            result = await session.call_tool(tool, arguments)
            payload = {
                "protocol_version": init.protocolVersion,
                "server": init.serverInfo.name,
            }
            if result.structuredContent is not None:
                payload["result"] = result.structuredContent
            else:
                text = "".join(
                    c.text for c in result.content if hasattr(c, "text"))
                try:
                    payload["result"] = json.loads(text)
                except (json.JSONDecodeError, ValueError):
                    payload["result"] = {"text": text}
            payload["is_error"] = bool(result.isError)
            return payload


async def _list_tools(url: str) -> dict:
    async with _connect(url) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            return {
                "protocol_version": init.protocolVersion,
                "server": init.serverInfo.name,
                "tools": [
                    {"name": t.name, "description": t.description,
                     "input_schema": t.inputSchema}
                    for t in tools.tools
                ],
            }


def call_tool(url: str, tool: str, arguments: dict) -> dict:
    """Blocking wrapper: initialize, call one tool, return its payload."""
    return asyncio.run(_call(url, tool, arguments))


def list_tools(url: str) -> dict:
    """Blocking wrapper: initialize, list the server's tools."""
    return asyncio.run(_list_tools(url))
