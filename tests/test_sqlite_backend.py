"""SQLite backend: interface semantics + persistence across instances."""
import pytest

from crew_memory.graphdb import MemoryBackend
from crew_memory.sqlite_backend import SQLiteBackend


def exercise(be):
    """Same op sequence against any backend; returns comparable results."""
    be.merge_node("Entity", "entity:maya", {"name": "Maya"})
    be.merge_node("Fact", "fact:1", {"text": "Maya is allergic to peanuts"})
    be.merge_edge("fact:1", "ABOUT", "entity:maya")
    be.merge_node("Fact", "fact:2", {"text": "Maya plays soccer"})
    be.merge_edge("fact:2", "ABOUT", "entity:maya")
    neigh = be.neighbors("entity:maya", "ABOUT", "in")
    paths = be.traverse("entity:maya", [("ABOUT", "in")])
    return {
        "nodes": be.node_count(),
        "edges": be.edge_count(),
        "neighbor_uids": sorted(n["uid"] for _, n in neigh),
        "path_uids": sorted(tuple(n["uid"] for n in p["nodes"]) for p in paths),
        "search": [n["uid"] for n in be.search_text("allergic")],
        "found": [n["uid"] for n in be.find_nodes("Fact")],
    }


def test_sqlite_parity_with_memory_backend(tmp_path):
    lite = SQLiteBackend(str(tmp_path / "g.db"))
    mem = MemoryBackend()
    assert exercise(lite) == exercise(mem)
    lite.close()


def test_persistence_across_instances(tmp_path):
    path = str(tmp_path / "g.db")
    first = SQLiteBackend(path)
    first.merge_node("Fact", "fact:x", {"text": "persisted across restarts"})
    first.close()
    second = SQLiteBackend(path)
    node = second.get_node("fact:x")
    assert node is not None
    assert node["props"]["text"] == "persisted across restarts"
    second.close()


def test_merge_edge_rejects_unknown_rel(tmp_path):
    be = SQLiteBackend(str(tmp_path / "g.db"))
    with pytest.raises(ValueError):
        be.merge_edge("a", "NOT_A_REL", "b")
    be.close()
