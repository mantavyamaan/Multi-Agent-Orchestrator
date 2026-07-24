"""Planner Node: Generates the execution DAG."""

from langchain_core.messages import SystemMessage
from src.state import MultiAgentState
from src.schemas import ExecutionPlan

PLANNER_PROMPT = """You are the master Task Planner for an enterprise agentic runtime.
Your job is to break down the user's objective into a highly optimized Directed Acyclic Graph (DAG) of sub-tasks.

You have access to the following capabilities that you can assign to tasks:
- "Search": Web and Wikipedia search
- "FileSystem": Reading and writing local files
- "Memory": Saving and retrieving long-term semantic context

CRITICAL RULES:
1. Output MUST be a valid ExecutionPlan matching the schema.
2. Break the work down into atomic, highly parallelizable tasks where possible.
3. If Task B depends on Task A, explicitly list Task A's ID in Task B's `dependencies`.
4. Be lean: do not create unnecessary steps.
"""

def make_planner_node(llm):
    # Bind the structured output schema to the LLM
    planner_llm = llm.with_structured_output(ExecutionPlan)

    def planner_node(state: MultiAgentState):
        messages = [SystemMessage(content=PLANNER_PROMPT)] + state.get("messages", [])
        
        # Actually, state["messages"] contains dicts (AgentMessage TypedDict), not Langchain Message objects.
        # Let's format them properly.
        lc_msgs = [SystemMessage(content=PLANNER_PROMPT)]
        for m in state.get("messages", []):
            lc_msgs.append(SystemMessage(content=f"{m['name']}: {m['content']}"))
            
        plan = planner_llm.invoke(lc_msgs)
        
        # Convert plan into our TaskState dictionary
        task_dict = {}
        for t in plan.tasks:
            task_dict[t.id] = {
                "id": t.id,
                "description": t.description,
                "required_capabilities": t.required_capabilities,
                "dependencies": t.dependencies,
                "status": "pending",
                "result": None,
                "worker_name": None
            }
            
        return {
            "tasks": task_dict,
            "status": "planned",
            "messages": [{"role": "system", "name": "Planner", "content": f"Generated DAG of {len(task_dict)} tasks."}]
        }

    return planner_node
