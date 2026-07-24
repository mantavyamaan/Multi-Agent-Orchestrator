"""Coder node — produces implementation artifacts (report §5.4, §5.9).

SECURITY NOTE (§10.1): generated code is an artifact in state. It must
never be executed on the orchestration host. Execution belongs in an
isolated, resource-limited sandbox added during the pilot.
"""

from typing import Any, Callable

from src.errors import ControlledNodeFailure, invoke_with_retry
from src.state import MultiAgentState
from src.schemas import CoderArtifact

SYSTEM_PROMPT = """You are an implementation specialist in a multi-agent workflow.
Using the user's objective and the researcher's findings already present in
the conversation, produce clean, working, well-commented code that satisfies
the request. Include brief usage notes. Do not perform new research.
"""

def make_coder_node(model: Any) -> Callable[[MultiAgentState], dict]:
    def coder_node(state: MultiAgentState) -> dict:
        payload = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *state["messages"],
        ]
        try:
            structured_model = model.with_structured_output(CoderArtifact)
            result = invoke_with_retry(lambda: structured_model.invoke(payload), node_name="coder")
            content = result.model_dump_json(indent=2)
        except ControlledNodeFailure as exc:
            return {"errors": [str(exc)], "status": "coder_failed"}

        return {
            "messages": [{"role": "assistant", "name": "coder", "content": content}],
        }

    return coder_node
