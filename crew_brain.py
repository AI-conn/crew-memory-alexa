"""CrewBrain — the tool-facing service layer over Crew Memory.

The MCP tools, the tests, and the demo seed all call this layer. It wraps
``MemoryService`` (vendored Crew Memory core) and adds the two things the
Alexa+ surface needs:

* **Evidence paths** — every recall/answer carries the actual graph chain it
  came from (who wrote it, in which session, what it is about). Answers are
  extractive: composed only from nodes in the graph. If the graph has no
  support, the answer says so instead of guessing — the same honesty rule
  as the original Crew Memory Q&A engine.
* **Multi-hop ask** — ``crew_ask`` expands one hop: facts that match the
  question, plus facts about the same entities those facts are ABOUT,
  plus matching procedures. That traversal is what separates this from a
  single-turn Q&A wrapper.
"""
from __future__ import annotations

from crew_memory.memory import AGENTS, MemoryService

VALID_AGENTS = tuple(AGENTS.keys())


def _display(node: dict) -> str:
    p = node["props"]
    return p.get("name") or p.get("title") or (p.get("text") or "")[:60] or node["uid"]


def _path(nodes: list[dict], rels: list[str]) -> dict:
    return {
        "nodes": [
            {"uid": n["uid"], "label": n["label"], "name": _display(n)} for n in nodes
        ],
        "rels": rels,
    }


class CrewBrain:
    def __init__(self, memory: MemoryService):
        self.mem = memory
        self.be = memory.be
        self._sessions: dict[str, str] = {}

    # -- internals --------------------------------------------------------
    def _session(self, agent_id: str) -> str:
        if agent_id not in self._sessions:
            self._sessions[agent_id] = self.mem.start_session(agent_id)
        return self._sessions[agent_id]

    def _evidence_for_fact(self, fact: dict) -> list[dict]:
        """Provenance + aboutness chains for one fact node."""
        paths = []
        agent_uid = f"agent:{fact['props'].get('agent', '')}"
        agent = self.be.get_node(agent_uid)
        session = self.be.get_node(fact["props"].get("session", ""))
        if agent and session:
            paths.append(_path([agent, fact, session], ["WROTE", "LEARNED_IN"]))
        elif agent:
            paths.append(_path([agent, fact], ["WROTE"]))
        for _, ent in self.be.neighbors(fact["uid"], "ABOUT", "out"):
            paths.append(_path([fact, ent], ["ABOUT"]))
        return paths

    # -- tools ------------------------------------------------------------
    def remember(self, agent_id: str, text: str, kind: str = "fact",
                 about: list[str] | None = None) -> dict:
        """Store something in crew memory.

        kind: "fact" (semantic), "episode" (episodic log), or "procedure"
        is handled by remember_procedure; procedures need steps, so here
        kind is fact|episode.
        """
        if agent_id not in VALID_AGENTS:
            raise ValueError(f"agent must be one of {VALID_AGENTS}")
        session = self._session(agent_id)
        entities = []
        for name in about or []:
            uid = f"entity:{name.strip().lower().replace(' ', '-')}"
            self.be.merge_node("Entity", uid, {"name": name})
            entities.append(uid)
        if kind == "episode":
            uid = self.mem.log_episode(agent_id, session, "note", text, about=entities)
            layer = "episodic"
        else:
            uid = self.mem.learn_fact(agent_id, session, text, about=entities,
                                      source="alexa-mcp")
            layer = "semantic"
        return {"stored": uid, "layer": layer, "agent": agent_id,
                "session": session, "about": about or []}

    def remember_procedure(self, agent_id: str, name: str, steps: list[str],
                           trigger: str = "") -> dict:
        if agent_id not in VALID_AGENTS:
            raise ValueError(f"agent must be one of {VALID_AGENTS}")
        session = self._session(agent_id)
        uid = self.mem.record_procedure(agent_id, session, name, steps, trigger)
        return {"stored": uid, "layer": "procedural", "agent": agent_id,
                "steps": len(steps)}

    def recall(self, query: str, limit: int = 10) -> dict:
        """Retrieve facts matching the query, each with its evidence path."""
        hits = self.mem.recall(query)[:limit]
        results = []
        for f in hits:
            results.append({
                "uid": f["uid"],
                "text": f["props"].get("text", ""),
                "kind": f["props"].get("kind", "fact"),
                "agent": f["props"].get("agent"),
                "created_at": f["props"].get("created_at"),
                "evidence": self._evidence_for_fact(f),
            })
        return {"query": query, "count": len(results), "results": results}

    def handoff(self, from_agent: str, to_agent: str, summary: str,
                references: list[str] | None = None,
                question: str | None = None) -> dict:
        """Pass context from one crew role to another through the graph."""
        for a in (from_agent, to_agent):
            if a not in VALID_AGENTS:
                raise ValueError(f"agent must be one of {VALID_AGENTS}")
        session = self._session(from_agent)
        refs = [r for r in (references or []) if self.be.get_node(r)]
        uid = self.mem.create_handoff(from_agent, to_agent, session, summary,
                                      refs, question)
        ctx = self.mem.handoff_context(uid)
        return {
            "handoff": uid, "from": from_agent, "to": to_agent,
            "status": "open",
            "context_nodes": [n["uid"] for n in ctx["references"]],
            "neighborhood_nodes": len(ctx["neighborhood"]),
        }

    def open_handoffs(self, agent_id: str) -> dict:
        hs = self.mem.open_handoffs(agent_id)
        return {
            "agent": agent_id, "count": len(hs),
            "handoffs": [
                {"uid": h["uid"], "summary": h["props"].get("summary", ""),
                 "question": h["props"].get("question", ""),
                 "from": h["props"].get("from_agent", ""),
                 "created_at": h["props"].get("created_at", "")}
                for h in hs
            ],
        }

    def complete_handoff(self, agent_id: str, handoff_uid: str,
                         result_text: str) -> dict:
        if agent_id not in VALID_AGENTS:
            raise ValueError(f"agent must be one of {VALID_AGENTS}")
        session = self._session(agent_id)
        self.mem.complete_handoff(handoff_uid, agent_id, session, result_text)
        return {"handoff": handoff_uid, "status": "done", "by": agent_id}

    def crew_ask(self, question: str) -> dict:
        """Multi-hop question over the memory graph, with evidence.

        Hop 1: facts matching the question text. Hop 2: other facts ABOUT
        the same entities. Plus procedures whose name/trigger matches.
        Answer text is composed only from graph contents.
        """
        direct = self.mem.recall(question)
        seen = {f["uid"] for f in direct}
        related: list[dict] = []
        entity_names: list[str] = []
        for f in direct:
            for _, ent in self.be.neighbors(f["uid"], "ABOUT", "out"):
                entity_names.append(_display(ent))
                for other in self.mem.facts(about_uid=ent["uid"]):
                    if other["uid"] not in seen:
                        seen.add(other["uid"])
                        related.append(other)
        procs = []
        q = question.lower()
        for p in self.mem.procedures():
            hay = (p["props"].get("name", "") + " " +
                   p["props"].get("trigger", "")).lower()
            if any(t in hay for t in q.split() if len(t) > 3) or q in hay:
                steps = self.mem.procedure_steps(p["uid"])
                procs.append({
                    "uid": p["uid"], "name": p["props"].get("name", ""),
                    "steps": [s["props"].get("text", "") for s in steps],
                })
        evidence: list[dict] = []
        for f in direct + related:
            evidence.extend(self._evidence_for_fact(f))
        lines = []
        for f in direct:
            lines.append(f["props"].get("text", ""))
        for f in related:
            lines.append("(related) " + f["props"].get("text", ""))
        for p in procs:
            lines.append(f"Procedure '{p['name']}': " + "; ".join(p["steps"]))
        answered = bool(lines)
        answer = (" ".join(lines) if answered else
                  "I don't have anything in crew memory that covers that yet. "
                  "Ask me to remember it, and it will be there next time.")
        return {
            "question": question, "answered": answered, "answer": answer,
            "direct_facts": len(direct), "related_facts": len(related),
            "procedures": len(procs), "entities": sorted(set(entity_names)),
            "evidence": evidence,
        }

    def stats(self) -> dict:
        return {
            "backend": self.be.name,
            "nodes": self.be.node_count(),
            "edges": self.be.edge_count(),
            "facts": len(self.be.find_nodes("Fact")),
            "episodes": len(self.be.find_nodes("Episode")),
            "procedures": len(self.be.find_nodes("Procedure")),
            "handoffs_open": len(self.be.find_nodes("Handoff", status="open")),
        }
