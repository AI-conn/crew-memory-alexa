"""SQLite graph backend — persistent local store for the Crew Memory graph.

NEW in this repo (not part of the original crew-memory-graph build).

Implements the exact ``GraphBackend`` interface from ``graphdb.py`` with the
same semantics as ``MemoryBackend``, but every write lands in a SQLite file,
so the crew's memory survives server restarts, new processes, and new
sessions. That persistence is the product claim of "Crew Memory for Alexa+":
an assistant that still knows what it learned yesterday.

Why SQLite and not FalkorDB here: the hackathon demo must run for judges
with one command and no external account or server. The FalkorDB backend
remains in ``graphdb.py`` as the production path; both implement the same
interface, and ``MemoryService`` cannot tell them apart.

Read paths (neighbors/traverse/search) are computed in Python over the
stored node/edge sets, mirroring ``MemoryBackend``'s algorithms line for
line, so behavior is identical across backends. The graph sizes this
targets (a household / small crew memory) make that entirely practical.
"""
from __future__ import annotations

import json
import sqlite3
import threading

from .graphdb import REL_TYPES, TEXT_PROPS, GraphBackend, _node


class SQLiteBackend(GraphBackend):
    """GraphBackend persisted to a single SQLite file."""

    name = "sqlite"

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS nodes "
            "(uid TEXT PRIMARY KEY, label TEXT NOT NULL, props TEXT NOT NULL)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS edges "
            "(src TEXT NOT NULL, rel TEXT NOT NULL, dst TEXT NOT NULL, "
            "props TEXT NOT NULL, UNIQUE(src, rel, dst))"
        )
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # -- writes ---------------------------------------------------------
    def clear(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM nodes")
            self._db.execute("DELETE FROM edges")
            self._db.commit()

    def merge_node(self, label: str, uid: str, props: dict) -> dict:
        with self._lock:
            row = self._db.execute(
                "SELECT props FROM nodes WHERE uid = ?", (uid,)
            ).fetchone()
            if row:
                merged = json.loads(row[0])
                merged.update(props)
                merged["uid"] = uid
                self._db.execute(
                    "UPDATE nodes SET props = ? WHERE uid = ?",
                    (json.dumps(merged), uid),
                )
                self._db.commit()
                return _node(uid, label, merged)
            node = _node(uid, label, props)
            self._db.execute(
                "INSERT INTO nodes (uid, label, props) VALUES (?, ?, ?)",
                (uid, label, json.dumps(node["props"])),
            )
            self._db.commit()
            return node

    def merge_edge(self, src_uid: str, rel: str, dst_uid: str,
                   props: dict | None = None) -> None:
        if rel not in REL_TYPES:
            raise ValueError(f"relationship type not in schema: {rel}")
        with self._lock:
            row = self._db.execute(
                "SELECT props FROM edges WHERE src = ? AND rel = ? AND dst = ?",
                (src_uid, rel, dst_uid),
            ).fetchone()
            if row:
                merged = json.loads(row[0])
                merged.update(props or {})
                self._db.execute(
                    "UPDATE edges SET props = ? WHERE src = ? AND rel = ? AND dst = ?",
                    (json.dumps(merged), src_uid, rel, dst_uid),
                )
            else:
                self._db.execute(
                    "INSERT INTO edges (src, rel, dst, props) VALUES (?, ?, ?, ?)",
                    (src_uid, rel, dst_uid, json.dumps(props or {})),
                )
            self._db.commit()

    def set_props(self, uid: str, props: dict) -> None:
        with self._lock:
            row = self._db.execute(
                "SELECT props FROM nodes WHERE uid = ?", (uid,)
            ).fetchone()
            if row:
                merged = json.loads(row[0])
                merged.update(props)
                self._db.execute(
                    "UPDATE nodes SET props = ? WHERE uid = ?",
                    (json.dumps(merged), uid),
                )
                self._db.commit()

    # -- reads ----------------------------------------------------------
    def get_node(self, uid: str) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT label, props FROM nodes WHERE uid = ?", (uid,)
            ).fetchone()
        if not row:
            return None
        return _node(uid, row[0], json.loads(row[1]))

    def all_nodes(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT uid, label, props FROM nodes").fetchall()
        return [_node(uid, label, json.loads(props)) for uid, label, props in rows]

    def all_edges(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT src, rel, dst, props FROM edges").fetchall()
        return [
            {"src": s, "rel": r, "dst": d, "props": json.loads(p)}
            for s, r, d, p in rows
        ]

    def find_nodes(self, label: str | None = None, **filters) -> list[dict]:
        out = []
        for n in self.all_nodes():
            if label and n["label"] != label:
                continue
            if all(n["props"].get(k) == v for k, v in filters.items()):
                out.append(n)
        return out

    def _adj(self, edges: list[dict], uid: str, rel: str | None, direction: str):
        for e in edges:
            if rel and e["rel"] != rel:
                continue
            if direction == "out" and e["src"] == uid:
                yield e, e["dst"]
            elif direction == "in" and e["dst"] == uid:
                yield e, e["src"]
            elif direction == "both" and e["src"] == uid:
                yield e, e["dst"]
            elif direction == "both" and e["dst"] == uid:
                yield e, e["src"]

    def neighbors(self, uid: str, rel: str | None = None,
                  direction: str = "out") -> list[tuple[dict, dict]]:
        nodes = {n["uid"]: n for n in self.all_nodes()}
        return [
            (e["props"], nodes[other])
            for e, other in self._adj(self.all_edges(), uid, rel, direction)
            if other in nodes
        ]

    def traverse(self, start_uid: str, steps: list[tuple[str, str]]) -> list[dict]:
        nodes = {n["uid"]: n for n in self.all_nodes()}
        edges = self.all_edges()
        if start_uid not in nodes:
            return []
        frontier = [{"nodes": [nodes[start_uid]], "rels": []}]
        for rel, direction in steps:
            nxt = []
            for path in frontier:
                last = path["nodes"][-1]["uid"]
                for e, other in self._adj(edges, last, rel, direction):
                    if other in nodes:
                        nxt.append({
                            "nodes": path["nodes"] + [nodes[other]],
                            "rels": path["rels"] + [e["rel"]],
                        })
            frontier = nxt
            if not frontier:
                break
        return frontier

    def search_text(self, text: str, limit: int = 25) -> list[dict]:
        q = text.lower()
        out = []
        for n in self.all_nodes():
            hay = " ".join(str(n["props"].get(p, "")) for p in TEXT_PROPS).lower()
            if q in hay:
                out.append(n)
                if len(out) >= limit:
                    break
        return out
