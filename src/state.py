"""Shared state and reducers for DAG execution.

Reducer policy:
  messages       -> append (operator.add)
  errors         -> append
  tasks          -> merge (dict update by task ID)
  status / count -> replace
"""

import operator
from typing import Annotated, Literal, TypedDict, Any

class AgentMessage(TypedDict):
    role: str
    name: str
    content: str

class TaskState(TypedDict):
    id: str
    description: str
    required_capabilities: list[str]
    dependencies: list[str]
    status: Literal["pending", "running", "completed", "failed"]
    result: str | None
    worker_name: str | None

def merge_tasks(left: dict[str, TaskState], right: dict[str, TaskState]) -> dict[str, TaskState]:
    """Merge tasks by updating status and results for existing IDs."""
    merged = left.copy()
    for k, v in right.items():
        merged[k] = v
    return merged

class MultiAgentState(TypedDict):
    messages: Annotated[list[AgentMessage], operator.add]
    task_id: str
    active_subtask_id: str
    step_count: int
    status: str
    errors: Annotated[list[str], operator.add]
    
    # DAG state
    tasks: Annotated[dict[str, TaskState], merge_tasks]

def initial_state(task: str, task_id: str) -> MultiAgentState:
    return {
        "messages": [{"role": "user", "name": "user", "content": task}],
        "task_id": task_id,
        "step_count": 0,
        "status": "running",
        "errors": [],
        "tasks": {},
    }
