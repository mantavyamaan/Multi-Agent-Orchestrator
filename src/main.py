"""CLI entry point.

Usage:
    python -m src.main "Research LangGraph and write a script for it"

Prints the full execution trace (auditable path, PR-07) followed by the
final user-facing answer, hiding coordination noise unless --verbose.
"""

import argparse
import logging
import uuid

from src.config import settings
from src.graph import build_graph
from src.llm import get_model
from src.state import initial_state

def run(task: str, verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    task_id = str(uuid.uuid4())[:8]
    app = build_graph(get_model())
    config = {
        "configurable": {"thread_id": task_id},
        # Framework-level hard stop — independent of the coordinator (§5.11)
        "recursion_limit": settings.max_steps * 3,
    }

    print(f"\n=== Run {task_id} | mode={settings.mode} ===")
    print(f"Task: {task}\n")
    print("--- Execution trace ---")

    trace: list[str] = []
    final_state = None
    for event in app.stream(initial_state(task, task_id), config=config):
        for node_name, update in event.items():
            trace.append(node_name)
            print(f"  -> {node_name}", end="")
            if node_name == "coordinator" and update and "next" in update:
                print(f"   [route: {update['next']}]", end="")
            print()
    final_state = app.get_state(config).values

    trace.append("END")
    print("\nObserved path: " + " -> ".join(["START"] + trace))
    print(f"Final status:  {final_state.get('status')}")
    print(f"Steps used:    {final_state.get('step_count')}/{settings.max_steps}")
    if final_state.get("errors"):
        print(f"Errors:        {final_state['errors']}")

    # User-facing output: last specialist contributions, not routing noise
    print("\n--- Final output ---")
    for msg in final_state["messages"]:
        if msg["name"] in ("researcher", "coder", "reviewer"):
            print(f"\n[{msg['name'].upper()}]\n{msg['content']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coordinator-driven multi-agent system")
    parser.add_argument(
        "task",
        nargs="?",
        default="Research LangGraph and write a script for it",
        help="Natural-language objective (PR-01)",
    )
    parser.add_argument("--verbose", action="store_true", help="Show routing logs")
    args = parser.parse_args()
    run(args.task, verbose=args.verbose)
