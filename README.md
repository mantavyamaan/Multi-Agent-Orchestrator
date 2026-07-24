# Multi-Agent Orchestrator

> **🌐 [Try the Live Demo →](https://mantavyamaan.github.io/Multi-Agent-Orchestrator/demo)**

**Production-grade** Enterprise AI Agentic Runtime built on LangGraph.
The orchestrator leverages a **Map-Reduce DAG architecture** where a master **Planner** dynamically splits user objectives into dependent subtasks. A **Scheduler** analyzes the dependency graph and dispatches tasks to parallel **Workers**. Workers dynamically bind tools from a centralized registry based on their assigned capabilities, and possess long-term semantic memory powered by ChromaDB.

## Architecture

```
START → Planner ─→ Scheduler ─┬─(Send)→ Worker (Search)     ─┐
                              ├─(Send)→ Worker (FileSystem) ─┼→ Scheduler → END
                              └─(Send)→ Worker (Memory)     ─┘
```

### Components
1. **Planner (`src/nodes/planner.py`)**: Uses Structured Outputs to break the user's objective into an optimized Directed Acyclic Graph (DAG) of atomic sub-tasks with strict dependencies.
2. **Scheduler (`src/nodes/scheduler.py`)**: Analyzes the graph state and dispatches ready tasks in parallel to generic workers using the LangGraph `Send` API.
3. **Parallel Workers (`src/nodes/worker.py`)**: A dynamic execution environment (ReAct agent) that automatically binds required tools (Search, FileSystem, Memory) on the fly to complete a task.
4. **Tool Registry (`src/tools/registry.py`)**: Central repository of agent capabilities.
5. **Semantic Memory (`src/memory/vectorstore.py`)**: Local ChromaDB instance providing Episodic and Semantic memory (saving and retrieving past contexts across sessions).

### Session Persistence
The orchestrator uses `AsyncSqliteSaver` to automatically persist graph state to a local `checkpoints.db`. This allows conversational contexts and multi-agent sessions to survive server restarts.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Unix/Mac
pip install -r requirements.txt
cp .env.example .env
```

### Web UI (recommended)

```bash
python -m src.api
```
Open `http://localhost:8000` — watch the DAG resolve in real-time with live trace, agent cards, and formatted results.

### CLI

```bash
python -m src.main "Research LangGraph and write a script for it" --verbose
```

### 🧠 Switching to Live LLM Mode (Real AI)

By default, the application runs in **Mock Mode** (`AGENT_MODE=mock`), which uses a deterministic dummy model. It is perfect for testing the UI and seeing how the orchestrator graphs route tasks. To make the agents actually think, write code, and execute your real prompts, switch to **Live Mode**.

1. **Create the Environment File**
   ```bash
   cp .env.example .env
   ```

2. **Configure the `.env` File**
   Open the `.env` file and set:
   - `AGENT_MODE=live`
   - `MODEL_PROVIDER=openai` (or `anthropic`, etc.)
   - Add your API key (e.g. `OPENAI_API_KEY=sk-...`)

3. **Restart the Server**
   ```bash
   python -m src.api
   ```

## Security & Safety Limits

| Layer | Implementation | Purpose |
|---|---|---|
| HTTP Headers | `Content-Security-Policy`, `X-Frame-Options` | Prevents XSS and clickjacking attacks |
| Frontend | `DOMPurify` | Sanitizes all LLM markdown before DOM insertion |
| DAG Cycles | `MAX_CONSECUTIVE_REPEATS` | Prevents infinite loops |
| Hallucination Prevention | Pydantic Schemas | Forces the Planner to emit strict structured JSON |
| Tool Isolation | Dynamic Registry | Workers are only granted the specific tools requested by the Planner |

## Project Structure

```
Multi-Agent Orchestrator/
├── src/
│   ├── api.py          # FastAPI server (SSE streaming)
│   ├── config.py       # pydantic-settings
│   ├── graph.py        # LangGraph StateGraph assembly (Map-Reduce)
│   ├── llm.py          # Model factories (Mock & Live)
│   ├── schemas.py      # Pydantic Schemas (ExecutionPlan, SubTask)
│   ├── state.py        # Shared state + reducers
│   ├── main.py         # CLI entry point
│   ├── memory/
│   │   └── vectorstore.py # ChromaDB integration
│   ├── tools/
│   │   └── registry.py    # Search, FileSystem, and Memory tools
│   └── nodes/
│       ├── planner.py
│       ├── scheduler.py
│       └── worker.py
├── static/
│   ├── index.html      # App shell
│   ├── style.css       # Glassmorphism dark UI
│   └── app.js          # SSE trace parsing
├── checkpoints.db      # LangGraph state persistence
└── chroma_db/          # Semantic Memory vector database
```
