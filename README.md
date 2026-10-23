# Crew Memory for Alexa+

**A self-hosted MCP server that gives a voice assistant a persistent, shared crew memory.**

Alexa+ hosts are stateless between conversations. Crew Memory is the missing
layer underneath: three crew roles — **Planner, Researcher, Executor** — read
and write one memory graph with three layers (**episodic** / **semantic** /
**procedural**). Anything one role learns is there for the others, in the next
session, after a server restart. Every answer carries its **evidence path**:
the actual chain of graph nodes it came from. If memory has no support for a
question, the crew says so instead of guessing.

Built for the Amazon "Build, Ship, Shape" Developer Hackathon — **Alexa+
track** (self-hosted MCP server) + **Open Source mini challenge**.

## Quick start (one command)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
bash run_all.sh
```

Open **http://127.0.0.1:5000** — the simulated Alexa+ experience. The MCP
server itself listens at **http://127.0.0.1:8000/mcp** (Streamable HTTP).
On first run the store is seeded with a fictional household scenario
(the Alvarez family — all data synthetic) so there is memory to explore.

Run the pieces separately:

```bash
.venv/bin/python mcp_server.py --port 8000        # the MCP server
.venv/bin/python seed_demo.py                     # seed / reseed the demo data
MCP_URL=http://127.0.0.1:8000/mcp .venv/bin/python alexa_sim.py   # the sim UI
.venv/bin/python -m pytest                        # the test suite
```

## The MCP surface

Implemented with the official **`mcp` Python SDK** (FastMCP) over
**Streamable HTTP**, negotiating **protocol version 2025-11-25**. The server
is the track artifact: the runtime hook is real — `mcp_server.py` imports the
SDK and registers every tool with it.

| Tool | What it does |
|---|---|
| `remember` | Store a fact (semantic) or episode (episodic) with provenance and ABOUT entities |
| `remember_procedure` | Store an ordered routine in procedural memory |
| `recall` | Retrieve facts matching a query — each with its evidence path |
| `crew_ask` | Multi-hop question: matching facts → facts about the same entities → procedures, answered extractively with evidence |
| `handoff` | Pass a task between crew roles through the graph; the receiver gets the referenced nodes plus their neighborhood as context |
| `open_handoffs` / `complete_handoff` | The crew's shared work queue |
| `memory_stats` | Counts by layer — the memory's vital signs |

Any MCP host (the Alexa+ runtime, the MCP Inspector, another agent) can
connect to `/mcp` and call the same tools. The web UI is only a demo host.

## Architecture

```
 voice host (Alexa+ / sim UI / any MCP client)
        │  MCP 2025-11-25 · Streamable HTTP · JSON-RPC
        ▼
 mcp_server.py ── FastMCP (official mcp SDK) ── tools
        ▼
 crew_brain.py ── tool-facing service: evidence paths, multi-hop ask
        ▼
 crew_memory/ ── MemoryService (episodic/semantic/procedural, handoffs)
        ▼
 GraphBackend ── sqlite_backend.py (persistent local store, new)
                 graphdb.FalkorDBBackend (production path, from the
                 original Crew Memory Graph build)
```

* **State across sessions** is the core property: sessions are cheap
  wrappers; the graph is the state. Proven by test — the suite restarts the
  server process mid-test and recalls what was remembered before.
* **Storage**: `SQLiteBackend` (new in this repo) implements the same
  `GraphBackend` interface as the original FalkorDB backend, so judges run
  everything locally with zero external accounts; FalkorDB remains the
  documented production path.
* **Honesty rule**: answers are composed only from graph contents. No
  language model sits between the tools and the memory, so nothing can be
  hallucinated into an answer — unsupported questions get "I don't have
  that yet."

## How this maps to the judging criteria

* **Tech Implementation** — a real MCP 2025-11-25 Streamable HTTP server on
  the official SDK (not a wrapper around a chat API); a persistent graph
  store behind a backend interface with two implementations; a protocol-level
  test suite (12 tests) that runs the actual initialize handshake, tool
  calls, handoff flow, and restart persistence.
* **Design** — the sim UI is built to make the invisible visible: the live
  tool call, the negotiated protocol version, and the evidence path render
  next to every answer, so a judge sees *why* the assistant knows something.
* **Potential Impact** — persistent, evidence-backed memory is the
  difference between a voice assistant that performs tasks and one that
  knows your household: allergies, routines, preferences, and open tasks,
  shared across every surface that connects to the server.
* **Quality of the Idea** — memory as crew infrastructure, not a feature:
  role handoffs through a graph mean the "assistant" is really a small team
  with a shared brain — the pattern our Crew Memory Graph already
  uses for software agents, brought to the voice surface.

## What was built during the submission window

The Crew Memory core (`crew_memory/graphdb.py`, `crew_memory/memory.py`)
pre-exists in [AI-conn/crew-memory-graph](https://github.com/AI-conn/crew-memory-graph)
(Graph Hacks, Oct 2026) and is vendored here under the same MIT license.
**New in this window:** the MCP server + tool surface, the SQLite persistent
backend, the CrewBrain evidence/multi-hop layer, the simulated Alexa+
experience, the demo scenario, the tests, and this documentation.

## The simulated experience — what is and isn't simulated

The web UI simulates the *host*: its intent routing is simple keyword
matching (labeled in the code), standing in for the Alexa+ runtime's own
NLU. Everything below that line is real: the MCP handshake, tool calls,
memory writes, traversal, evidence, and persistence all execute for every
message. If the MCP server is down, the UI says so — it never fakes an
answer.

## Product feedback & friction log

See **FRICTION-LOG.md** — kept from day one, in the required format.
Short version: the SDK is genuinely good to build on; the sharp edges we
hit (client rename deprecations, proxy-env interference with localhost
servers, settings-before-run ordering) are documented there with
workarounds.

## License

House license — see `LICENSE`. © 2026 AI-conn.
