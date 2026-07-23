"""Coordinator node (report §5.7, §5.11).

Control responsibilities only — it performs no specialist work.
Enforces, independently of the LLM:
  1. Step limit
  2. Error threshold
  3. Repeated-route (ineffective cycle) detection
Logical termination ('finish') and human cancellation are handled by the
route mapping and the runtime respectively.

Message pruning:
  When the message list grows beyond MESSAGE_WINDOW, older non-essential
  coordinator messages are pruned before sending to the LLM. This prevents
  context window overflow in long-running live-mode sessions.
"""

import logging
from typing import Any, Callable

from src.config import settings
from src.errors import ControlledNodeFailure, invoke_with_retry
from src.schemas import RouteDecision
from src.state import AgentMessage, MultiAgentState

logger = logging.getLogger(__name__)

# Keep the latest N messages when the context grows too large.
# The user message (index 0) is always preserved.
MESSAGE_WINDOW = 20

SYSTEM_INSTRUCTION = """You coordinate a bounded workflow.

Available workers:
• researcher: obtains and synthesizes evidence.
• coder: creates or revises implementation code.
• reviewer: checks evidence, code, safety, and requirement coverage.
• finish: use only when the objective is satisfied or execution must stop.

Rules:
• Do not repeat a worker without a clear unresolved need.
• Route to 'reviewer' before finishing if code or research has not been reviewed.
• Return only the required structured decision.
"""


def repeated_cycle(route_history: list[str]) -> bool:
    n = settings.max_consecutive_repeats
    if len(route_history) < n:
        return False
    tail = route_history[-n:]
    return len(set(tail)) == 1 and tail[0] != "finish"


def _prune_messages(messages: list[AgentMessage]) -> list[AgentMessage]:
    """Trim the message list to MESSAGE_WINDOW entries.

    Always preserves the very first message (user objective) so the LLM
    never loses sight of the original goal, then keeps the most recent
    MESSAGE_WINDOW - 1 messages to stay within context limits.
    """
    if len(messages) <= MESSAGE_WINDOW:
        return messages

    # Keep the original user objective + the most recent context
    head = messages[:1]               # user task (always preserved)
    tail = messages[-(MESSAGE_WINDOW - 1):]
    pruned_count = len(messages) - MESSAGE_WINDOW
    logger.info(
        "Context pruning: dropped %d older messages to stay within window=%d",
        pruned_count, MESSAGE_WINDOW,
    )
    return head + tail


def make_coordinator_node(model: Any) -> Callable[[MultiAgentState], dict]:
    router = model.with_structured_output(RouteDecision)

    def coordinator_node(state: MultiAgentState) -> dict:
        # --- Independent safety guards (never delegated to the LLM) ---
        if state["step_count"] >= settings.max_steps:
            logger.warning("Step limit reached (%d). Forcing finish.", settings.max_steps)
            return {"next": "finish", "status": "stopped_step_limit"}

        if len(state["errors"]) >= settings.max_errors:
            logger.warning("Error threshold reached. Forcing finish.")
            return {"next": "finish", "status": "stopped_error_threshold"}

        if repeated_cycle(state["route_history"]):
            logger.warning("Repeated ineffective cycle detected. Forcing finish.")
            return {"next": "finish", "status": "stopped_repeated_cycle"}

        # --- Build pruned payload (§2.2 context safety) ---
        pruned = _prune_messages(state["messages"])
        payload = [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            *pruned,
        ]

        try:
            decision: RouteDecision = invoke_with_retry(
                lambda: router.invoke(payload), node_name="coordinator"
            )
        except ControlledNodeFailure as exc:
            return {
                "next": "finish",
                "status": "failed_routing",
                "errors": [str(exc)],
            }

        logger.info("route=%s reason=%s", decision.next, decision.reason)
        return {
            "next": decision.next,
            "status": f"route:{decision.next}",
            "step_count": state["step_count"] + 1,
            "route_history": [decision.next],
            "messages": [
                {
                    "role": "assistant",
                    "name": "coordinator",
                    "content": f"Routing to '{decision.next}': {decision.reason}",
                }
            ],
        }

    return coordinator_node


def route_from_coordinator(state: MultiAgentState) -> str:
    return state["next"]
