"""Model factory — production-grade (report §7.3).

Live mode uses LangChain's provider-agnostic langchain.chat_models.init_chat_model.
Mock mode is deterministic and costs nothing — use it for tests and demos.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.config import settings
from src.schemas import ExecutionPlan, SubTask

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock implementation (AGENT_MODE=mock)
# ---------------------------------------------------------------------------

@dataclass
class MockResponse:
    content: str


class MockStructuredPlanner:
    """Deterministic Planner for testing."""
    def invoke(self, messages: list[dict[str, Any]] | list[Any]) -> ExecutionPlan:
        return ExecutionPlan(
            tasks=[
                SubTask(
                    id="t1",
                    description="Mock research task",
                    required_capabilities=["Search"],
                    dependencies=[]
                ),
                SubTask(
                    id="t2",
                    description="Mock write file task",
                    required_capabilities=["FileSystem"],
                    dependencies=["t1"]
                )
            ]
        )


@dataclass
class MockChatModel:
    """Minimal stand-in implementing the interface the nodes rely on."""

    def with_structured_output(self, schema: type) -> Any:
        if schema is ExecutionPlan:
            return MockStructuredPlanner()
        raise ValueError(f"No mock available for schema {schema!r}")
        
    def bind_tools(self, tools: list[Any]) -> Any:
        return self

    def invoke(self, messages: list[dict[str, Any]] | list[Any]) -> MockResponse:
        return MockResponse("Mock worker response: Task executed successfully.")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _get_live_model(model_name: str) -> Any:
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

    try:
        from langchain.chat_models import init_chat_model
    except ImportError:
        from langchain_community.chat_models import init_chat_model  # type: ignore[no-redef]

    logger.info("Model mode: live | provider=%s model=%s", provider, model_name)
    return init_chat_model(
        model_name,
        model_provider=settings.model_provider,
        temperature=0,
    )

def get_router_model() -> Any:
    if settings.mode == "mock":
        logger.info("Router model mode: mock (no API calls)")
        return MockChatModel()
    return _get_live_model(settings.router_model_name)

def get_worker_model() -> Any:
    if settings.mode == "mock":
        logger.info("Worker model mode: mock (no API calls)")
        return MockChatModel()
    return _get_live_model(settings.worker_model_name)
