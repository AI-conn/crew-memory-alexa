"""Crew Memory core — shared, layered memory for a multi-agent crew.

Layers: episodic (what happened), semantic (learned facts),
procedural (how we do things). The graph is the state; sessions are cheap
wrappers around it, so memory survives across sessions and processes.

This package is vendored from AI-conn/crew-memory-graph (MIT, same author)
for the "Crew Memory for Alexa+" hackathon build. New in this repo:
``sqlite_backend`` (persistent local store), the MCP server, and the
simulated Alexa+ front end.
"""

__version__ = "0.2.0"
