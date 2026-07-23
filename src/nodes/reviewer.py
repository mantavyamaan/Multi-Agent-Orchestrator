"""Reviewer node — independent quality gate (report §5.10)."""

from typing import Any, Callable

from src.errors import ControlledNodeFailure, invoke_with_retry
from src.schemas import ReviewDecision
from src.state import MultiAgentState

SYSTEM_PROMPT = """You are an independent reviewer in a multi-agent workflow.
Evaluate the work produced so far against the user's original objective.
Check: requirement coverage, factual support, internal consistency,
code correctness, security issues, and unresolved assumptions.
Return your structured verdict. Choose 'revise' only when a concrete,
fixable deficiency exists; name the agent that must fix it.
"""

def make_reviewer_node(model: Any) -> Callable[[MultiAgentState], dict]:
    reviewer = model.with_structured_output(ReviewDecision)

    def reviewer_node(state: MultiAgentState) -> dict:
        payload = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *state["messages"],
        ]
        try:
            verdict: ReviewDecision = invoke_with_retry(
                lambda: reviewer.invoke(payload), node_name="reviewer"
            )
        except ControlledNodeFailure as exc:
            return {"errors": [str(exc)], "status": "reviewer_failed"}

        findings = "; ".join(verdict.findings) or "No findings."
        return {
            "messages": [
                {
                    "role": "assistant",
                    "name": "reviewer",
                    "content": (
                        f"REVIEW VERDICT: {verdict.verdict}. "
                        f"Findings: {findings} "
                        f"Required next agent: {verdict.required_next_agent}."
                    ),
                }
            ],
        }

    return reviewer_node
