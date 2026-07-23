"""Graph assembly (report §7.3, §5.2).

Topology:
    START -> coordinator
    coordinator --(conditional)--> researcher | coder | reviewer | END
    every worker --(fixed edge)--> coordinator   (§7.5)

Persistence:
    Uses AsyncSqliteSaver for async (FastAPI/astream) contexts and
    MemorySaver for sync (CLI/tests) contexts.
    AsyncSqliteSaver requires: pip install aiosqlite langgraph-checkpoint-sqlite
"""

import logging
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.nodes.coder import make_coder_node
from src.nodes.coordinator import make_coordinator_node, route_from_coordinator
from src.nodes.researcher import make_researcher_node
from src.nodes.reviewer import make_reviewer_node
from src.state import MultiAgentState

logger = logging.getLogger(__name__)

# Path for the SQLite checkpoint database — stored alongside the project root
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "checkpoints.db")


def _get_async_checkpointer():
    """Return an AsyncSqliteSaver context manager, or None if unavailable.
    
    Usage (inside async with):
        async with _get_async_checkpointer() as cp:
            graph = build_graph(model, checkpointer=cp)
    """
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        logger.info("Checkpointer: AsyncSqliteSaver (path=%s)", _DB_PATH)
        return AsyncSqliteSaver.from_conn_string(_DB_PATH)
    except ImportError:
        logger.warning(
            "aiosqlite not installed — falling back to MemorySaver. "
            "Install with: pip install aiosqlite langgraph-checkpoint-sqlite"
        )
        return None


def build_graph(model: Any, checkpointer: Any | None = None):
    """Build and compile the LangGraph StateGraph.
    
    Args:
        model: The LLM model instance (mock or live).
        checkpointer: An already-instantiated checkpoint saver.
                      When None, uses MemorySaver (suitable for sync/test contexts).
                      For async (FastAPI), supply an AsyncSqliteSaver instance.
    """
    graph = StateGraph(MultiAgentState)

    graph.add_node("coordinator", make_coordinator_node(model))
    graph.add_node("researcher", make_researcher_node(model))
    graph.add_node("coder", make_coder_node(model))
    graph.add_node("reviewer", make_reviewer_node(model))

    graph.add_edge(START, "coordinator")

    # Mandatory return edges: every worker hands control back (§7.5)
    graph.add_edge("researcher", "coordinator")
    graph.add_edge("coder", "coordinator")
    graph.add_edge("reviewer", "coordinator")

    graph.add_conditional_edges(
        "coordinator",
        route_from_coordinator,
        {
            "researcher": "researcher",
            "coder": "coder",
            "reviewer": "reviewer",
            "finish": END,
        },
    )

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return graph.compile(checkpointer=saver)
