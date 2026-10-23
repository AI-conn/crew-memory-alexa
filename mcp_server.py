"""Crew Memory for Alexa+ — MCP server (Streamable HTTP).

A self-hosted Model Context Protocol server built on the official ``mcp``
Python SDK (FastMCP), speaking MCP over Streamable HTTP. Protocol version
is negotiated by the SDK with the connecting host; SDK 1.28's latest is
2025-11-25, the version the Alexa+ track requires.

The server gives a voice-assistant host a *persistent, shared crew memory*:
three crew roles (planner / researcher / executor) read and write one memory
graph with three layers (episodic / semantic / procedural). Every retrieval
carries its evidence path — the actual chain of graph nodes the answer came
from — and memory lives in a local SQLite file, so it survives restarts and
sessions. This is deliberately not a single-turn Q&A wrapper: state is
maintained across sessions, roles hand context to each other through the
graph, and questions are answered by multi-hop traversal.

Run:
    python mcp_server.py [--host 127.0.0.1] [--port 8000] [--db crew_memory.db]

MCP endpoint: http://<host>:<port>/mcp   Health: GET /
"""
from __future__ import annotations

import argparse
import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from crew_brain import CrewBrain
from crew_memory.memory import MemoryService
from crew_memory.sqlite_backend import SQLiteBackend

DB_PATH = os.environ.get("CREW_MEMORY_DB", "crew_memory.db")

backend = SQLiteBackend(DB_PATH)
brain = CrewBrain(MemoryService(backend))

mcp = FastMCP(
    "crew-memory-alexa",
    instructions=(
        "Persistent crew memory for a household assistant. Use `remember` to "
        "store facts the user tells you, `recall` to retrieve them with "
        "evidence, `crew_ask` for questions that need the crew's combined "
        "memory, and `handoff` to pass a task between crew roles."
    ),
)


@mcp.custom_route("/", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({
        "service": "crew-memory-alexa",
        "transport": "streamable-http",
        "mcp_endpoint": "/mcp",
        "stats": brain.stats(),
    })


@mcp.tool()
def remember(text: str, kind: str = "fact", about: list[str] | None = None,
             agent: str = "researcher") -> dict:
    """Store something in the crew's shared memory so it persists across sessions.

    text: the fact or note to store, in plain words.
    kind: "fact" (semantic memory — things that are true) or "episode"
          (episodic memory — something that happened).
    about: names of people/things this is about (powers later retrieval).
    agent: which crew role is recording it: planner | researcher | executor.
    """
    return brain.remember(agent, text, kind=kind, about=about)


@mcp.tool()
def remember_procedure(name: str, steps: list[str], trigger: str = "",
                       agent: str = "planner") -> dict:
    """Store a reusable procedure (an ordered routine) in procedural memory."""
    return brain.remember_procedure(agent, name, steps, trigger)


@mcp.tool()
def recall(query: str, limit: int = 10) -> dict:
    """Retrieve stored facts matching a query.

    Every result includes its evidence path: the graph chain (who recorded
    it, in which session, what it is about) the memory came from.
    """
    return brain.recall(query, limit=limit)


@mcp.tool()
def crew_ask(question: str) -> dict:
    """Ask the crew a question answered from shared memory by traversal.

    Multi-hop: facts that match, facts about the same entities, and matching
    procedures. The answer is composed only from memory contents and ships
    with evidence paths; if memory has no support, it says so.
    """
    return brain.crew_ask(question)


@mcp.tool()
def handoff(from_agent: str, to_agent: str, summary: str,
            references: list[str] | None = None, question: str = "") -> dict:
    """Hand a task/context from one crew role to another through the graph.

    references: uids of memory nodes (from remember/recall) the receiver
    needs; the receiver gets those nodes plus their neighborhood as context.
    Crew roles: planner | researcher | executor.
    """
    return brain.handoff(from_agent, to_agent, summary,
                         references=references, question=question or None)


@mcp.tool()
def open_handoffs(agent: str) -> dict:
    """List open handoffs addressed to a crew role (planner|researcher|executor)."""
    return brain.open_handoffs(agent)


@mcp.tool()
def complete_handoff(agent: str, handoff_uid: str, result: str) -> dict:
    """Mark a handoff done and record the outcome in episodic memory."""
    return brain.complete_handoff(agent, handoff_uid, result)


@mcp.tool()
def memory_stats() -> dict:
    """Counts of what the crew currently remembers, by layer."""
    return brain.stats()


def main() -> None:
    ap = argparse.ArgumentParser(description="Crew Memory MCP server")
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("PORT", "8000")))
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()
    if args.db != DB_PATH:
        # Rebind to the requested store before serving.
        global backend, brain
        backend = SQLiteBackend(args.db)
        brain = CrewBrain(MemoryService(backend))
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
