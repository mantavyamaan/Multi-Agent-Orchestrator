"""Worker Node: Dynamically binds tools and executes a subtask."""

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from src.state import MultiAgentState
from src.tools.registry import get_tools_for_capabilities

def make_worker_node(llm):
    def worker_node(state: MultiAgentState):
        subtask_id = state.get("active_subtask_id")
        if not subtask_id:
            return {}
            
        task = state["tasks"][subtask_id]
        
        # 1. Discover tools dynamically
        tools = get_tools_for_capabilities(task["required_capabilities"])
        
        # 2. Execute using a dynamic ReAct agent
        prompt = f"""You are executing a subtask within a larger DAG execution.
Task ID: {task['id']}
Description: {task['description']}

You have been granted capabilities: {task['required_capabilities']}

Do your best to complete the objective using your tools. Return a clear, comprehensive final answer."""
        
        if tools:
            agent = create_react_agent(llm, tools=tools)
            result_state = agent.invoke({"messages": [SystemMessage(content=prompt)]})
            final_output = result_state["messages"][-1].content
        else:
            result_state = llm.invoke([SystemMessage(content=prompt)])
            final_output = result_state.content
            
        # 3. Update task state
        updated_task = task.copy()
        updated_task["status"] = "completed"
        updated_task["result"] = final_output
        updated_task["worker_name"] = "DynamicWorker"
        
        return {
            "tasks": {subtask_id: updated_task},
            "messages": [{"role": "system", "name": f"Worker-{subtask_id}", "content": f"Task {subtask_id} completed:\n{final_output}"}]
        }
        
    return worker_node
