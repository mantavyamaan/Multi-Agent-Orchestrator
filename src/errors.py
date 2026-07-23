"""Error classification and bounded retry (report §7.6).

Provides both a synchronous and an asynchronous retry helper so that
nodes running inside an async FastAPI event loop do not block it with
time.sleep (which is a critical production bug in the original code).

Retries are always bounded — uncontrolled retries amplify cost and outages.
"""

import asyncio
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
BACKOFF_SECONDS = 1.5


class ControlledNodeFailure(Exception):
    """Raised when a node cannot continue after bounded recovery attempts."""


def invoke_with_retry(fn: Callable[[], Any], node_name: str) -> Any:
    """Synchronous bounded retry with exponential backoff.

    Safe to use in tests and CLI (sync) contexts only.
    For async contexts (FastAPI), use invoke_with_retry_async.
    """
    last_exc: Exception | None = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "node=%s attempt=%d/%d error=%s",
                node_name, attempt + 1, 1 + MAX_RETRIES, exc,
            )
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_SECONDS * (attempt + 1))
    raise ControlledNodeFailure(
        f"{node_name} failed after {1 + MAX_RETRIES} attempts: {last_exc}"
    ) from last_exc


async def invoke_with_retry_async(fn: Callable[[], Any], node_name: str) -> Any:
    """Async bounded retry — uses asyncio.sleep to avoid blocking the event loop.

    Use this version from async node wrappers when running under FastAPI.
    """
    last_exc: Exception | None = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "node=%s attempt=%d/%d error=%s",
                node_name, attempt + 1, 1 + MAX_RETRIES, exc,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(BACKOFF_SECONDS * (attempt + 1))
    raise ControlledNodeFailure(
        f"{node_name} failed after {1 + MAX_RETRIES} attempts: {last_exc}"
    ) from last_exc
