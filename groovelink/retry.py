"""Retry strategies for GrooveLink."""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any, Callable

from groovelink.exceptions import RetryExhaustedError
from groovelink.utils import build_jitter_backoff, current_time


class RetryStrategy(Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    ) -> None:
        self.max_retries = max_retries
        self.strategy = strategy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number (0-indexed)."""
        if self.strategy == RetryStrategy.FIXED:
            return self.base_delay
        if self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)
        else:  # EXPONENTIAL
            delay = build_jitter_backoff(
                self.base_delay, self.max_delay, self.jitter
            )(attempt)
        return min(delay, self.max_delay)


class RetryController:
    """Execute a callable with retry logic."""

    def __init__(self, config: RetryConfig) -> None:
        self.config = config

    def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute a function synchronously with retries."""
        last_exception: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except self.config.retryable_exceptions as exc:
                last_exception = exc
                if attempt >= self.config.max_retries:
                    break
                delay = self.config.get_delay(attempt)
                time.sleep(delay)
        raise RetryExhaustedError(
            f"Failed after {self.config.max_retries + 1} attempts."
        ) from last_exception

    async def execute_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute a function asynchronously with retries."""
        last_exception: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
            except self.config.retryable_exceptions as exc:
                last_exception = exc
                if attempt >= self.config.max_retries:
                    break
                delay = self.config.get_delay(attempt)
                await asyncio.sleep(delay)
        raise RetryExhaustedError(
            f"Failed after {self.config.max_retries + 1} attempts."
        ) from last_exception
