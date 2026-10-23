"""End-to-end MCP protocol tests against the live server (Streamable HTTP).

These go through the official SDK client: real initialize handshake, real
tools/list, real tools/call — the same path the Alexa+ host would take.
"""
import mcp_client
from tests.conftest import Server


def test_protocol_version_and_tool_list(server):
    listing = mcp_client.list_tools(server.url)
    assert listing["protocol_version"] == "2025-11-25"
    assert listing["server"] == "crew-memory-alexa"
    names = {t["name"] for t in listing["tools"]}
    assert {"remember", "remember_procedure", "recall", "crew_ask",
            "handoff", "open_handoffs", "complete_handoff",
            "memory_stats"} <= names


def test_remember_recall_roundtrip_with_evidence(server):
    stored = mcp_client.call_tool(server.url, "remember", {
        "text": "Uncle Theo takes the train in on Friday nights.",
        "about": ["Theo"], "agent": "researcher"})["result"]
    assert stored["layer"] == "semantic"

    got = mcp_client.call_tool(server.url, "recall",
                               {"query": "Theo"})["result"]
    assert got["count"] == 1
    hit = got["results"][0]
    assert "train" in hit["text"]
    rels = [r for path in hit["evidence"] for r in path["rels"]]
    assert "WROTE" in rels and "LEARNED_IN" in rels and "ABOUT" in rels


def test_crew_ask_multihop_and_honest_no_answer(server):
    mcp_client.call_tool(server.url, "remember", {
        "text": "Maya is allergic to peanuts.", "about": ["Maya"]})
    mcp_client.call_tool(server.url, "remember", {
        "text": "Soccer practice is on Thursdays at 5 pm.", "about": ["Maya"]})
    ans = mcp_client.call_tool(server.url, "crew_ask", {
        "question": "What is Maya allergic to?"})["result"]
    assert ans["answered"] is True
    assert "peanuts" in ans["answer"]
    # hop 2: the soccer fact shares the Maya entity, so it is related context
    assert ans["related_facts"] >= 1
    assert ans["evidence"]

    none = mcp_client.call_tool(server.url, "crew_ask", {
        "question": "What is the capital of Norway?"})["result"]
    assert none["answered"] is False


def test_handoff_flow(server):
    fact = mcp_client.call_tool(server.url, "remember", {
        "text": "The pantry is out of rice.", "about": ["Pantry"]})["result"]
    h = mcp_client.call_tool(server.url, "handoff", {
        "from_agent": "planner", "to_agent": "executor",
        "summary": "Restock rice before Sunday",
        "references": [fact["stored"]],
        "question": "Anything else low?"})["result"]
    assert h["status"] == "open"

    open_ = mcp_client.call_tool(server.url, "open_handoffs",
                                 {"agent": "executor"})["result"]
    assert open_["count"] == 1
    assert open_["handoffs"][0]["uid"] == h["handoff"]

    done = mcp_client.call_tool(server.url, "complete_handoff", {
        "agent": "executor", "handoff_uid": h["handoff"],
        "result": "Two bags of rice bought and shelved."})["result"]
    assert done["status"] == "done"

    open2 = mcp_client.call_tool(server.url, "open_handoffs",
                                 {"agent": "executor"})["result"]
    assert open2["count"] == 0


def test_memory_survives_server_restart(server):
    mcp_client.call_tool(server.url, "remember", {
        "text": "The spare key lives with the neighbors, the Patels.",
        "about": ["Patels"]})
    server.stop()
    Server.start(server)  # same db file, new process
    try:
        got = mcp_client.call_tool(server.url, "recall",
                                   {"query": "spare key"})["result"]
        assert got["count"] == 1
        assert "Patels" in got["results"][0]["text"]
    finally:
        server.stop()
