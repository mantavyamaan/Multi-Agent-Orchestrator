import json
import os

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

# Ensure we run in mock mode — must be set before importing src.api
os.environ.setdefault("AGENT_MODE", "mock")

from src.api import app


@pytest.fixture(scope="module")
def client():
    """Inject MemorySaver so tests don't attempt AsyncSqliteSaver,
    which is incompatible with the synchronous TestClient event loop.
    """
    app.state.checkpointer_override = MemorySaver()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.state.checkpointer_override = None



# ---------------------------------------------------------------------------
# Health & status endpoints
# ---------------------------------------------------------------------------

def test_health_returns_ok(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["mode"] == "mock"
    assert body["graph_ready"] is True


def test_status_returns_mode(client):
    res = client.get("/api/status")
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "mock"
    assert "max_steps" in body
    assert "rate_limit" in body


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_run_rejects_empty_task(client):
    res = client.post("/api/run", json={"task": ""})
    assert res.status_code == 422


def test_run_rejects_whitespace_only_task(client):
    res = client.post("/api/run", json={"task": "   "})
    assert res.status_code == 422


def test_run_rejects_task_too_short(client):
    res = client.post("/api/run", json={"task": "hi"})
    assert res.status_code == 422


def test_run_rejects_task_too_long(client):
    res = client.post("/api/run", json={"task": "x" * 2001})
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Streaming execution
# ---------------------------------------------------------------------------

def _collect_events(response_text: str) -> list[dict]:
    """Parse SSE response body into a list of data JSON objects."""
    events = []
    for line in response_text.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def test_run_streams_expected_nodes(client):
    """The mock run should stream coordinator, researcher, coder, reviewer, END."""
    res = client.post(
        "/api/run",
        json={"task": "Research LangGraph and write a script for it"},
        headers={"Accept": "text/event-stream"},
    )
    assert res.status_code == 200
    events = _collect_events(res.text)
    nodes = [e["node"] for e in events]

    # Must contain these node names in order
    assert "coordinator" in nodes
    assert "researcher" in nodes
    assert "coder" in nodes
    assert "reviewer" in nodes
    assert nodes[-1] == "END"


def test_run_end_event_contains_meta(client):
    """The END event must carry timing and step metadata."""
    res = client.post(
        "/api/run",
        json={"task": "Research LangGraph and write a script for it"},
    )
    events = _collect_events(res.text)
    end_event = next((e for e in events if e["node"] == "END"), None)
    assert end_event is not None
    assert "meta" in end_event
    assert end_event["meta"]["step_count"] > 0
    assert end_event["meta"]["elapsed_seconds"] >= 0


def test_run_end_event_contains_messages(client):
    """The END event update must include the message history."""
    res = client.post(
        "/api/run",
        json={"task": "Research LangGraph and write a script for it"},
    )
    events = _collect_events(res.text)
    end_event = next((e for e in events if e["node"] == "END"), None)
    assert end_event is not None
    msgs = end_event.get("update", {}).get("messages", [])
    names = [m["name"] for m in msgs]
    assert "researcher" in names
    assert "coder" in names
    assert "reviewer" in names
