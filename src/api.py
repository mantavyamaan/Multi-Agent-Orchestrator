"""Production-grade FastAPI backend for the Multi-Agent Orchestrator.

Improvements over the initial version:
  - Singleton compiled graph — built once at startup, reused across all requests
  - Input validation (min/max length, whitespace-only rejection)
  - Safe state serializer — no json.dumps crash on non-serializable LangGraph types
  - CORS middleware for cross-origin frontends
  - Rate limiting via slowapi (configurable via settings.rate_limit)
  - /api/health endpoint for uptime monitoring
  - /api/status endpoint returning current mode and limits
  - Execution timing included in final END event payload
  - Structured error responses
"""

import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from src.config import settings
from src.graph import build_graph, _get_async_checkpointer
from src.llm import get_model
from src.state import initial_state

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Lifespan — build the singleton graph once at startup
# ---------------------------------------------------------------------------
_graph_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph_app
    logger.info("Building LangGraph application (mode=%s)...", settings.mode)
    try:
        model = get_model()
        # Allow tests (or integration harnesses) to inject their own checkpointer
        # by setting app.state.checkpointer_override before startup.
        override = getattr(app.state, "checkpointer_override", None)
        if override is not None:
            _graph_app = build_graph(model, checkpointer=override)
            logger.info("Graph ready (override checkpointer).")
            yield
        else:
            # Production path: try AsyncSqliteSaver, fall back to MemorySaver
            sqlite_cm = _get_async_checkpointer()
            if sqlite_cm is not None:
                async with sqlite_cm as cp:
                    _graph_app = build_graph(model, checkpointer=cp)
                    logger.info("Graph ready (AsyncSqliteSaver).")
                    yield
            else:
                _graph_app = build_graph(model)
                logger.info("Graph ready (MemorySaver fallback).")
                yield
    except Exception as exc:
        logger.critical("Failed to build graph at startup: %s", exc)
        raise
    finally:
        _graph_app = None


app = FastAPI(
    title="Multi-Agent Orchestrator",
    description="Coordinator-driven hub-and-spoke multi-agent system built on LangGraph.",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Lock down to specific origins in deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Content Security Policy middleware (plan §3.2)
# Prevents inline script injection and XSS at the HTTP header level.
# ---------------------------------------------------------------------------
_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
    "font-src 'self' https://fonts.gstatic.com; "
    "connect-src 'self'; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'self';"
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = _CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# Input sanitizer (plan §3.3)
# Strips HTML tags and non-printable control characters from the task string
# before it enters the graph, preventing prompt-injection vectors.
# ---------------------------------------------------------------------------
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HTML_TAG_RE = re.compile(r"<[^>]+>")

def _sanitize_task(text: str) -> str:
    """Remove HTML tags and ASCII control characters from user input."""
    text = _HTML_TAG_RE.sub("", text)       # strip HTML
    text = _CONTROL_CHARS_RE.sub("", text)  # strip control chars
    return text.strip()

# ---------------------------------------------------------------------------
# Safe serializer — prevents json.dumps crashes on non-serializable types
# ---------------------------------------------------------------------------
def _safe_serialize(obj: Any) -> Any:
    """Recursively converts a LangGraph state dict to a JSON-safe structure."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(i) for i in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    # Fallback: convert anything else to its string representation
    return str(obj)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    task: str = Field(..., min_length=10, max_length=2000)

    @field_validator("task")
    @classmethod
    def not_whitespace(cls, v: str) -> str:
        v = _sanitize_task(v)   # strip HTML and control chars (§3.3)
        if not v.strip():
            raise ValueError("task must contain non-whitespace content")
        if len(v) < 10:
            raise ValueError("task must be at least 10 characters after sanitization")
        return v


# ---------------------------------------------------------------------------
# SSE streaming generator
# ---------------------------------------------------------------------------
async def stream_orchestrator(task: str, task_id: str) -> AsyncGenerator[str, None]:
    config = {
        "configurable": {"thread_id": task_id},
        "recursion_limit": settings.max_steps * 3,
    }
    state = initial_state(task, task_id)
    start_time = time.monotonic()

    try:
        async for event in _graph_app.astream(state, config=config):
            for node_name, update in event.items():
                data = {"node": node_name, "update": _safe_serialize(update)}
                yield json.dumps(data)

        # Final state — send timing metadata alongside results
        final = _graph_app.get_state(config).values
        elapsed = round(time.monotonic() - start_time, 2)
        yield json.dumps({
            "node": "END",
            "update": _safe_serialize(final),
            "meta": {
                "task_id": task_id,
                "elapsed_seconds": elapsed,
                "step_count": final.get("step_count", 0),
                "status": final.get("status", "unknown"),
                "error_count": len(final.get("errors", [])),
            },
        })
        logger.info(
            "task_id=%s status=%s steps=%d elapsed=%.2fs",
            task_id, final.get("status"), final.get("step_count", 0), elapsed,
        )
    except Exception as exc:
        logger.error("task_id=%s stream error: %s", task_id, exc)
        yield json.dumps({"node": "ERROR", "error": str(exc)})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    """Uptime and readiness check."""
    return {
        "status": "ok",
        "mode": settings.mode,
        "graph_ready": _graph_app is not None,
    }


@app.get("/api/status")
async def status():
    """Returns current configuration limits — useful for the UI mode badge."""
    return {
        "mode": settings.mode,
        "model_name": settings.model_name if settings.mode == "live" else "mock",
        "model_provider": settings.model_provider if settings.mode == "live" else "mock",
        "max_steps": settings.max_steps,
        "max_errors": settings.max_errors,
        "rate_limit": settings.rate_limit,
    }


@app.post("/api/run")
@limiter.limit(settings.rate_limit)
async def run_orchestrator(request: Request, body: RunRequest):
    if _graph_app is None:
        raise HTTPException(status_code=503, detail="Graph not initialized. Check server logs.")
    task_id = str(uuid.uuid4())[:8]
    logger.info("task_id=%s task='%.80s...'", task_id, body.task)
    return EventSourceResponse(stream_orchestrator(body.task, task_id))


# ---------------------------------------------------------------------------
# Static frontend — mounted last so API routes take priority
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=False)
