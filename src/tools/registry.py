"""Central registry for capability-driven tools."""
import os
import uuid
from langchain_core.tools import tool
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

from src.memory.vectorstore import semantic_memory

# 1. Search Tools
wiki = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())

@tool
def web_search(query: str) -> str:
    """Use this to search the web for current events or facts."""
    return f"Mock search result for: {query}"

@tool
def wikipedia_search(query: str) -> str:
    """Use this to search Wikipedia for established knowledge."""
    try:
        return wiki.run(query)
    except Exception as e:
        return f"Wikipedia search failed: {e}"

# 2. FileSystem Tools
@tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file at the given path."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Failed to write file: {e}"

@tool
def read_file(file_path: str) -> str:
    """Read content from a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Failed to read file: {e}"

# 3. Memory Tools
@tool
def save_memory(content: str) -> str:
    """Save an important fact or finding to long-term semantic memory for future retrieval."""
    mem_id = str(uuid.uuid4())
    semantic_memory.save(mem_id, content)
    return f"Memory saved with ID {mem_id}"

@tool
def search_memory(query: str) -> str:
    """Search long-term semantic memory for past facts or context."""
    results = semantic_memory.search(query)
    if not results:
        return "No relevant memories found."
    return "\n\n".join([f"Memory {i+1}: {res}" for i, res in enumerate(results)])

# Capability Registry
TOOL_REGISTRY = {
    "Search": [web_search, wikipedia_search],
    "FileSystem": [write_file, read_file],
    "Memory": [save_memory, search_memory],
}

def get_tools_for_capabilities(capabilities: list[str]):
    """Fetch all LangChain tools associated with the requested capabilities."""
    tools = []
    for cap in capabilities:
        if cap in TOOL_REGISTRY:
            tools.extend(TOOL_REGISTRY[cap])
    return tools
