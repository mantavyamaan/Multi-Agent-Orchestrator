"""Shared state and reducers (report §5.5, §5.6).

Reducer policy:
  messages       -> append (operator.add) — history is never replaced
  errors         -> append
  route_history  -> append (enables repeated-state detection, §5.11 #5)
  next / status  -> replace (last write wins, default behavior)
  step_count     -> replace (coordinator owns the increment)
"""

from operator import add
from typing import Annotated, Literal, TypedDict

class AgentMessage(TypedDict):
    role: str
    name: str
    content: str

Route = Literal["researcher", "coder", "reviewer", "finish"]

class MultiAgentState(TypedDict):
    messages: Annotated[list[AgentMessage], add]
    next: Route
    task_id: str
    step_count: int
    status: str
    errors: Annotated[list[str], add]
    route_history: Annotated[list[str], add]

def initial_state(task: str, task_id: str) -> MultiAgentState:
    return {
        "messages": [{"role": "user", "name": "user", "content": task}],
        "next": "researcher",
        "task_id": task_id,
        "step_count": 0,
        "status": "running",
        "errors": [],
        "route_history": [],
    }
