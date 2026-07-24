# Multi-Agent Orchestrator

> **🌐 [Try the Live Demo →](https://mantavyamaan.github.io/Multi-Agent-Orchestrator/demo)**

**Production-grade** coordinator-driven hub-and-spoke multi-agent AI system built on LangGraph.
A central Coordinator routes work between specialist agents (Researcher, Coder, Reviewer) over a shared graph state, with real-time streaming to a glassmorphism web UI.

## Architecture

```
START → Coordinator ─┬→ Researcher → Coordinator
                     ├→ Coder      → Coordinator
                     ├→ Reviewer   → Coordinator
                     └→ END
```

### Session Persistence
The orchestrator uses `AsyncSqliteSaver` to automatically persist graph state to a local `checkpoints.db`. This allows conversational contexts and multi-agent sessions to survive server restarts. During synchronous CLI usage or testing, it gracefully falls back to an ephemeral `MemorySaver`.

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
Open **http://localhost:8000** — watch agents work in real-time with live trace, agent cards, and formatted results.

### CLI

```bash
python -m src.main "Research LangGraph and write a script for it" --verbose
```

### 🧠 Switching to Live LLM Mode (Real AI)

By default, the application runs in **Mock Mode** (`AGENT_MODE=mock`), which uses a hardcoded, deterministic dummy model that costs nothing and requires no API keys. It is perfect for testing the UI and seeing how the orchestrator graphs route tasks.

To make the agents actually think, write code, and execute your real prompts, you must switch to **Live Mode**.

**Step-by-Step Guide:**

1. **Create the Environment File**
   If you haven't already, copy the template file to create your own configuration file:
   ```bash
   cp .env.example .env
   ```

2. **Configure the `.env` File**
   Open the newly created `.env` file in your code editor and change the following settings:
   - Change `AGENT_MODE=mock` to `AGENT_MODE=live`.
   - Ensure `MODEL_PROVIDER` is set to your preferred provider (e.g., `openai`, `anthropic`).
   - Add your real, active API key for that provider.

   *Example of a working `.env` file for OpenAI:*
   ```env
   AGENT_MODE=live
   MODEL_PROVIDER=openai
   ROUTER_MODEL_NAME=gpt-4o-mini
   WORKER_MODEL_NAME=gpt-4o
   OPENAI_API_KEY=sk-proj-your-real-api-key-here...
   ```

3. **Restart the Server**
   If your FastAPI server is currently running, stop it (press `Ctrl + C` in the terminal). 
   Then, start it back up:
   ```bash
   python -m src.api
   ```

4. **Verify in the UI**
   Open `http://localhost:8000`. In the top-left corner of the sidebar, the Mode Badge should now have a green dot and say **"Live · router:gpt-4o-mini | worker:gpt-4o"** (or whichever models you chose). When you submit a task now, the real LLM will process it!

## Tests

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

| Test file | What it covers |
|---|---|
| `tests/test_graph.py` | Graph correctness, routing, safety limits (5 tests) |
| `tests/test_api.py`   | API endpoints, input validation, SSE streaming (9 tests) |

## Security & Safety Limits

### Security Measures

| Layer | Implementation | Purpose |
|---|---|---|
| HTTP Headers | `Content-Security-Policy`, `X-Frame-Options` | Prevents XSS and clickjacking attacks |
| User Input | Regex Sanitizer | Strips HTML and control characters before entering the graph |
| Frontend | `DOMPurify` | Sanitizes all LLM markdown before DOM insertion |

### Execution Safety Limits (§5.11)

| Mechanism | Setting | Implementation |
|---|---|---|
| Step limit | `MAX_STEPS` | Enforced in code *before* the LLM is consulted |
| Repeated-cycle detection | `MAX_CONSECUTIVE_REPEATS` | `route_history` tail check |
| Error threshold | `MAX_ERRORS` | Forces controlled shutdown |
| Invalid routing | — | Pydantic schema + bounded retry |
| Hallucination Prevention | — | Structured Outputs (`.with_structured_output()`) enforced via Pydantic schemas |
| Rate limiting | `RATE_LIMIT` | slowapi per-IP limiter on `/api/run` |
| Human cancellation | — | UI Abort button / Ctrl-C |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Readiness + mode check |
| GET | `/api/status` | Current config (mode, model, limits) |
| POST | `/api/run` | Stream SSE execution trace |

## Project Structure

```
Multi-Agent Orchestrator/
├── src/
│   ├── api.py          # FastAPI server (CORS, rate limit, singleton graph)
│   ├── config.py       # pydantic-settings with validators
│   ├── errors.py       # Bounded sync + async retry helpers
│   ├── graph.py        # LangGraph StateGraph assembly
│   ├── llm.py          # Separate Router/Worker model factories (Mock & Live)
│   ├── schemas.py      # Pydantic Schemas (RouteDecision, ReviewDecision, ResearchArtifact, CoderArtifact)
│   ├── state.py        # Shared state + reducers
│   ├── main.py         # CLI entry point
│   └── nodes/
│       ├── coordinator.py
│       ├── researcher.py
│       ├── coder.py
│       └── reviewer.py
├── static/
│   ├── index.html      # App shell (sidebar, agent cards, trace panel)
│   ├── style.css       # Glassmorphism dark UI + responsive layout
│   └── app.js          # SSE streaming, toasts, copy, history, abort
├── tests/
│   ├── test_graph.py   # Graph-level hypothesis tests
│   └── test_api.py     # HTTP integration tests
├── requirements.txt
├── .env.example
└── README.md
```
