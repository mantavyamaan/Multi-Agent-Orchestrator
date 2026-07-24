"""Scheduler Node: Analyzes dependencies and triggers parallel workers."""

from langgraph.types import Send
from src.state import MultiAgentState

def scheduler_node(state: MultiAgentState):
    tasks = state.get("tasks", {})
    
    # 1. Are all tasks completed?
    if all(t["status"] == "completed" for t in tasks.values()):
        return {"status": "finished"}

    # 2. Find tasks that are ready to run (pending, and all deps are completed)
    ready_tasks = []
    for t_id, t in tasks.items():
        if t["status"] == "pending":
            # Check dependencies
            deps_completed = all(
                tasks[dep_id]["status"] == "completed" 
                for dep_id in t["dependencies"] 
                if dep_id in tasks
            )
            if deps_completed:
                ready_tasks.append(t)
    
    # Update state: mark ready tasks as 'running'
    updates = {}
    for t in ready_tasks:
        updated_t = t.copy()
        updated_t["status"] = "running"
        updates[t["id"]] = updated_t

    return {
        "tasks": updates,
        "status": "scheduling"
    }

def route_from_scheduler(state: MultiAgentState):
    """LangGraph conditional edge from Scheduler."""
    if state.get("status") == "finished":
        return "finish"
    
    tasks = state.get("tasks", {})
    running_tasks = [t for t in tasks.values() if t["status"] == "running"]
    
    if not running_tasks:
        # Deadlock or empty tasks
        return "finish"
        
    # Map-Reduce: Send parallel payloads to the worker node
    sends = []
    for t in running_tasks:
        sends.append(Send("worker", {"active_subtask_id": t["id"]}))
        
    return sends
