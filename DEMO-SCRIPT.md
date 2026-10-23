# Demo video script — Crew Memory for Alexa+ (target: under 3 minutes)

Format rules: public YouTube/Vimeo, English, show the project functioning,
no third-party trademarks or copyrighted music. Record at 1080p with the
browser zoomed so the "Under the hood" panel is readable.

**Setup (before recording):** fresh store —
`rm -f crew_memory.db* && bash run_all.sh` (seeds the Alvarez scenario),
browser open at http://127.0.0.1:5000, a terminal visible for the restart beat.

| Time | Screen | Narration / action |
|---|---|---|
| 0:00–0:15 | Sim UI | "Voice assistants forget everything between conversations. Crew Memory is an MCP server that gives Alexa+ a persistent crew memory — three roles, one shared brain, and every answer shows its evidence." |
| 0:15–0:40 | Click chip: "What food allergies do I need to remember?" | Answer appears with the evidence path in the side panel. "It knows Maya is allergic to peanuts — and here's the proof: the Researcher wrote it, in that session. Not a guess; a graph path." Point at protocol line: "MCP 2025-11-25, Streamable HTTP, official SDK." |
| 0:40–1:05 | Click chip: "What do we do on school mornings?" | "Procedural memory — a routine the Planner stored. Notice the routine itself respects the allergy: peanut-free lunchbox. Memory layers compose." |
| 1:05–1:30 | Type: "Remember that Leo is lactose intolerant" → then ask "What do I need to know about Leo?" | "New fact, stored live through a real tools/call. And the ask finds it in the next breath — same session or next month's." |
| 1:30–2:00 | Click chip: "Hand off to the executor: plan Sunday's groceries…" then "What's pending for the executor?" | "Roles hand work to each other through the graph, with the memory context attached. The Executor picks it up from any session — that's the crew pattern from our Crew Memory Graph, on the voice surface." |
| 2:00–2:25 | Terminal: stop the server, restart it, re-ask the allergy question in the UI | "Kill the server. Restart it. The memory is still there — it lives in a local graph store, not in a process. Swap in FalkorDB — the original build's backend, documented as the production path — and the same memory runs there." |
| 2:25–2:50 | Show repo + `pytest` summary (12 passed) | "Everything you saw is one command to run, open source, MIT — and covered by protocol-level tests, including the restart you just watched. Crew Memory for Alexa+: memory an assistant can prove." |

**Fallbacks:** if a live beat misfires, the same beats are covered by the
test suite; re-record the single beat rather than the whole video.
