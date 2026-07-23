# Multi-Agent Orchestrator

**Production-grade** coordinator-driven hub-and-spoke multi-agent AI system built on LangGraph.
A central Coordinator routes work between specialist agents (Researcher, Coder, Reviewer) over a shared graph state, with real-time streaming to a glassmorphism web UI.

## Architecture

```
START → Coordinator ─┬→ Researcher → Coordinator
                     ├→ Coder      → Coordinator
                     ├→ Reviewer   → Coordinator
                     └→ END
```

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

### Live LLM mode

Edit `.env`:
```env
AGENT_MODE=live
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o-mini
OPENAI_API_KEY=sk-...
```
Then re-run either command above.

## Tests

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

| Test file | What it covers |
|---|---|
| `tests/test_graph.py` | Graph correctness, routing, safety limits (5 tests) |
| `tests/test_api.py`   | API endpoints, input validation, SSE streaming (8 tests) |

## Safety Limits (§5.11)

| Mechanism | Setting | Implementation |
|---|---|---|
| Step limit | `MAX_STEPS` | Enforced in code *before* the LLM is consulted |
| Repeated-cycle detection | `MAX_CONSECUTIVE_REPEATS` | `route_history` tail check |
| Error threshold | `MAX_ERRORS` | Forces controlled shutdown |
| Invalid routing | — | Pydantic schema + bounded retry |
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
│   ├── llm.py          # Mock/live model factory
│   ├── schemas.py      # RouteDecision, ReviewDecision (Pydantic)
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
