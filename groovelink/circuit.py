"""Circuit breaker implementation."""

from __future__ import annotations

import json
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from groovelink.exceptions import CircuitBreakerOpenError
from groovelink.utils import current_time


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Thread-safe circuit breaker with optional JSON state persistence."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        expected_exception: type[Exception] = Exception,
        state_file: str | Path | None = None,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.expected_exception = expected_exception
        self.state_file = Path(state_file) if state_file else None

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._lock = threading.Lock()
        self._half_open_calls = 0

        self._load_state()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Call a function guarded by the circuit breaker."""
        with self._lock:
            self._update_state()
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit '{self.name}' is OPEN. Try again later."
                )
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit '{self.name}' is OPEN (half-open limit reached)."
                    )
                self._half_open_calls += 1

        try:
            result = func(*args, **kwargs)
        except self.expected_exception as exc:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result

    async def call_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Async variant of call."""
        import asyncio

        loop = asyncio.get_running_loop()
        # State check is synchronous/locked
        with self._lock:
            self._update_state()
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit '{self.name}' is OPEN. Try again later."
                )
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit '{self.name}' is OPEN (half-open limit reached)."
                    )
                self._half_open_calls += 1

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await loop.run_in_executor(None, lambda: func(*args, **kwargs))
        except self.expected_exception as exc:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result

    def _update_state(self) -> None:
        if self._state == CircuitState.OPEN:
            if self._last_failure_time is None:
                return
            if current_time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._success_count = 0
                self._failure_count = 0

    def _on_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    self._half_open_calls = 0
            else:
                self._failure_count = 0
            self._save_state()

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = current_time()
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
            self._save_state()

    def _save_state(self) -> None:
        if not self.state_file:
            return
        try:
            data = {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
                "half_open_calls": self._half_open_calls,
            }
            self.state_file.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass

    def _load_state(self) -> None:
        if not self.state_file:
            return
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            self._state = CircuitState(data.get("state", "closed"))
            self._failure_count = data.get("failure_count", 0)
            self._success_count = data.get("success_count", 0)
            self._last_failure_time = data.get("last_failure_time")
            self._half_open_calls = data.get("half_open_calls", 0)
        except Exception:
            pass
