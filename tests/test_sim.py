"""Simulated Alexa+ front end, exercised end-to-end against the live server."""
import os

import pytest


@pytest.fixture()
def sim(server, monkeypatch):
    monkeypatch.setenv("MCP_URL", server.url)
    import alexa_sim
    alexa_sim.app.config.update(TESTING=True)
    return alexa_sim.app.test_client()


def test_index_loads(sim):
    r = sim.get("/")
    assert r.status_code == 200
    assert b"Crew Memory for Alexa+" in r.data


def test_tools_endpoint_reports_live_server(sim):
    r = sim.get("/api/tools")
    assert r.status_code == 200
    body = r.get_json()
    assert body["protocol_version"] == "2025-11-25"
    assert any(t["name"] == "remember" for t in body["tools"])


def test_chat_remember_then_ask(sim):
    r1 = sim.post("/api/chat", json={
        "message": "Remember that the library books are due on Friday"})
    assert r1.status_code == 200
    j1 = r1.get_json()
    assert j1["tool"] == "remember"
    assert j1["protocol_version"] == "2025-11-25"
    assert "stored in crew memory" in j1["reply"]

    r2 = sim.post("/api/chat", json={
        "message": "What do you remember about the library books?"})
    j2 = r2.get_json()
    assert j2["tool"] == "recall"
    assert "Friday" in j2["reply"]


def test_chat_honest_when_server_down(monkeypatch):
    monkeypatch.setenv("MCP_URL", "http://127.0.0.1:9/mcp")
    import alexa_sim
    client = alexa_sim.app.test_client()
    r = client.post("/api/chat", json={"message": "What do you remember?"})
    assert r.status_code == 502
    assert "can't reach the Crew Memory server" in r.get_json()["reply"]
