"""Researcher node — gathers and organizes information (report §5.4).

In live mode this is where approved, permission-scoped search tools
attach (§10.1 tool gateway). External content must be treated as
untrusted data, never as instructions.
"""

from typing import Any, Callable

from src.errors import ControlledNodeFailure, invoke_with_retry
from src.state import MultiAgentState
from src.schemas import ResearchArtifact

SYSTEM_PROMPT = """You are a research specialist in a multi-agent workflow.
Your only job is to gather, compare, and synthesize the information needed
for the user's objective. Be factual, structured, and concise.
Cite what is established fact versus what is inference.
Do NOT write implementation code — that is the coder's responsibility.
"""

def make_researcher_node(model: Any) -> Callable[[MultiAgentState], dict]:
    def researcher_node(state: MultiAgentState) -> dict:
        payload = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *state["messages"],
        ]
        try:
            structured_model = model.with_structured_output(ResearchArtifact)
            result = invoke_with_retry(
                lambda: structured_model.invoke(payload), node_name="researcher"
            )
            content = result.model_dump_json(indent=2)
        except ControlledNodeFailure as exc:
            return {"errors": [str(exc)], "status": "researcher_failed"}

        return {
            "messages": [
                {"role": "assistant", "name": "researcher", "content": content}
            ],
        }

    return researcher_node
