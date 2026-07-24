"""Graph assembly for dynamic DAG execution."""
import logging
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.nodes.planner import make_planner_node
from src.nodes.scheduler import scheduler_node, route_from_scheduler
from src.nodes.worker import make_worker_node
from src.state import MultiAgentState

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "checkpoints.db")

def _get_async_checkpointer():
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        return AsyncSqliteSaver.from_conn_string(_DB_PATH)
    except ImportError:
        return None

def build_graph(router_model: Any, worker_model: Any, checkpointer: Any | None = None):
    """Build and compile the LangGraph StateGraph."""
    graph = StateGraph(MultiAgentState)

    graph.add_node("planner", make_planner_node(router_model))
    graph.add_node("scheduler", scheduler_node)
    graph.add_node("worker", make_worker_node(worker_model))

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "scheduler")
    
    # Conditional edge from scheduler using Send() for map-reduce
    graph.add_conditional_edges(
        "scheduler", 
        route_from_scheduler, 
        {"finish": END, "worker": "worker"}
    )
    
    # After a worker finishes, it must route back to the scheduler to check dependencies
    graph.add_edge("worker", "scheduler")

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return graph.compile(checkpointer=saver)
