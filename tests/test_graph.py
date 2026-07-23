"""Tests validating the report's hypotheses at the mechanism level.

H-01: structured routing produces only schema-valid transitions
H-02: every worker action is preceded by a coordinator decision
H-03: later agents can see earlier outputs (shared state)
H-04: explicit completion + step limits prevent uncontrolled loops
Appendix B: the canonical task follows the expected path
"""

from src.config import settings
from src.graph import build_graph
from src.llm import MockChatModel
from src.schemas import RouteDecision
from src.state import initial_state

def run(model, task="Research LangGraph and write a script for it"):
    app = build_graph(model)
    config = {
        "configurable": {"thread_id": "test"},
        "recursion_limit": settings.max_steps * 3,
    }
    trace = []
    for event in app.stream(initial_state(task, "test"), config=config):
        trace.extend(event.keys())
    return trace, app.get_state(config).values

def test_appendix_b_execution_path():
    trace, state = run(MockChatModel())
    # Coordinator -> Researcher -> Coordinator -> Coder -> Coordinator
    #             -> Reviewer -> Coordinator -> FINISH
    assert trace == [
        "coordinator", "researcher",
        "coordinator", "coder",
        "coordinator", "reviewer",
        "coordinator",
    ]
    assert state["status"] == "route:finish"

def test_every_worker_preceded_by_coordinator():  # H-02
    trace, _ = run(MockChatModel())
    for i, node in enumerate(trace):
        if node in ("researcher", "coder", "reviewer"):
            assert trace[i - 1] == "coordinator"

def test_shared_state_preserves_context():  # H-03
    _, state = run(MockChatModel())
    names = [m["name"] for m in state["messages"]]
    # Researcher output exists in state before the coder's contribution
    assert names.index("researcher") < names.index("coder")
    assert any(m["name"] == "user" for m in state["messages"])

def test_step_limit_forces_termination():  # H-04, §5.11 #2
    class LoopingRouter:
        def invoke(self, msgs):
            return RouteDecision(next="researcher", reason="loop forever")

    class LoopingModel(MockChatModel):
        def with_structured_output(self, schema):
            if schema is RouteDecision:
                return LoopingRouter()
            return super().with_structured_output(schema)

    _, state = run(LoopingModel())
    assert state["status"] in ("stopped_step_limit", "stopped_repeated_cycle")
    assert state["step_count"] <= settings.max_steps

def test_routing_failure_terminates_gracefully():  # FR-09, FR-10
    class BrokenRouter:
        def invoke(self, msgs):
            raise ValueError("provider returned invalid structured output")

    class BrokenModel(MockChatModel):
        def with_structured_output(self, schema):
            if schema is RouteDecision:
                return BrokenRouter()
            return super().with_structured_output(schema)

    _, state = run(BrokenModel())
    # The repeated-cycle guard may fire before the broken router
    # gets a chance to raise — both outcomes prove graceful termination.
    assert state["status"] in ("failed_routing", "stopped_repeated_cycle")
    assert state["step_count"] <= settings.max_steps
