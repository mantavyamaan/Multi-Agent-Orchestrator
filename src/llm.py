"""Model factory — production-grade (report §7.3).

Live mode uses LangChain's provider-agnostic langchain.chat_models.init_chat_model,
keeping business logic vendor-portable (nonfunctional requirement: Portability).

Mock mode is deterministic and costs nothing — use it for tests and demos.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.config import settings
from src.schemas import ReviewDecision, RouteDecision

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock implementation (AGENT_MODE=mock)
# ---------------------------------------------------------------------------

@dataclass
class MockResponse:
    content: str


class MockStructuredRouter:
    """Deterministic Coordinator brain for the PoC trace (Appendix B)."""

    def invoke(self, messages: list[dict[str, Any]]) -> RouteDecision:
        seen = {m.get("name") for m in messages if isinstance(m, dict)}
        if "researcher" not in seen:
            return RouteDecision(
                next="researcher",
                reason="The task requires external evidence before implementation.",
            )
        if "coder" not in seen:
            return RouteDecision(
                next="coder",
                reason="Research is complete; an implementation is still required.",
            )
        if "reviewer" not in seen:
            return RouteDecision(
                next="reviewer",
                reason="An independent quality gate must check the result.",
            )
        return RouteDecision(
            next="finish",
            reason="Research, implementation, and review are complete.",
        )


class MockStructuredReviewer:
    def invoke(self, messages: list[dict[str, Any]]) -> ReviewDecision:
        return ReviewDecision(
            verdict="pass",
            findings=["Mock review: requirement coverage and consistency verified."],
            required_next_agent="coordinator",
        )


@dataclass
class MockChatModel:
    """Minimal stand-in implementing the interface the nodes rely on."""

    canned: dict[str, str] = field(default_factory=dict)

    def with_structured_output(self, schema: type) -> Any:
        if schema is RouteDecision:
            return MockStructuredRouter()
        if schema is ReviewDecision:
            return MockStructuredReviewer()
        raise ValueError(f"No mock available for schema {schema!r}")

    def invoke(self, messages: list[dict[str, Any]]) -> MockResponse:
        system = next(
            (m["content"] for m in messages if m.get("role") == "system"), ""
        )
        if "research specialist" in system:
            return MockResponse(
                "Research result (mock): LangGraph models workflows as a "
                "StateGraph of nodes and edges over a shared typed state. "
                "Conditional edges select transitions at runtime; reducers "
                "control how node updates merge into state; compiled graphs "
                "support checkpointing and cyclic control flow."
            )
        if "implementation specialist" in system:
            return MockResponse(
                "Code result (mock):\n"
                "```python\n"
                "from langgraph.graph import StateGraph, START, END\n"
                "# Minimal LangGraph script derived from the research above\n"
                "```"
            )
        return MockResponse("Mock model response.")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_model() -> Any:
    if settings.mode == "mock":
        logger.info("Model mode: mock (no API calls)")
        return MockChatModel()

    # Live mode — validate that a key exists before making any calls
    import os
    provider = settings.model_provider.lower()
    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google_vertexai": "GOOGLE_API_KEY",
        "azure_openai": "AZURE_OPENAI_API_KEY",
    }
    required_key = key_map.get(provider)
    if required_key and not os.getenv(required_key):
        raise EnvironmentError(
            f"AGENT_MODE=live with MODEL_PROVIDER={provider} requires {required_key} "
            f"to be set in the environment or .env file."
        )

    # Provider-specific initialization isolated here so business logic
    # does not depend on any one vendor SDK (nonfunctional: Portability).
    try:
        from langchain.chat_models import init_chat_model
    except ImportError:
        from langchain_community.chat_models import init_chat_model  # type: ignore[no-redef]

    logger.info("Model mode: live | provider=%s model=%s", provider, settings.model_name)
    return init_chat_model(
        settings.model_name,
        model_provider=settings.model_provider,
        temperature=0,
    )
