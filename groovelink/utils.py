"""Shared helpers for GrooveLink."""

from __future__ import annotations

import random
import time
from typing import Any, Callable


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of headers with sensitive values redacted."""
    if not headers:
        return {}
    sensitive = {"authorization", "cookie", "x-api-key", "api-key", "token"}
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key in sensitive or lower_key.endswith("-token") or lower_key.endswith("-key"):
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value
    return redacted


def build_jitter_backoff(
    base_delay: float,
    max_delay: float,
    jitter: bool = True,
) -> Callable[[int], float]:
    """Build an exponential backoff function with optional jitter."""

    def compute(attempt: int) -> float:
        delay = base_delay * (2**attempt)
        if jitter:
            delay = random.uniform(0, delay)
        return min(delay, max_delay)

    return compute


def current_time() -> float:
    """Return monotonic time for internal timing."""
    return time.monotonic()


class HookRegistry:
    """Simple registry for event hooks."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable[..., Any]]] = {}

    def register(self, event: str, callback: Callable[..., Any]) -> None:
        """Register a callback for an event."""
        self._hooks.setdefault(event, []).append(callback)

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event to all registered callbacks."""
        for callback in self._hooks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception:
                pass
