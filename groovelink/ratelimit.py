"""Token bucket rate limiter with per-domain and global limits."""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Dict

from groovelink.exceptions import RateLimitExceededError


@dataclass
class BucketConfig:
    """Configuration for a token bucket."""

    rate: float  # tokens per second
    capacity: float  # max burst size


class TokenBucket:
    """Thread-safe token bucket."""

    def __init__(self, config: BucketConfig) -> None:
        self._config = config
        self._tokens = config.capacity
        self._last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0, timeout: float | None = None) -> bool:
        """Try to acquire tokens. Return True if successful."""
        deadline = time.monotonic() + timeout if timeout else None
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_update
                self._tokens = min(self._config.capacity, self._tokens + elapsed * self._config.rate)
                self._last_update = now

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True

            if deadline is None:
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.1, remaining))

    def acquire_blocking(self, tokens: float = 1.0) -> None:
        """Acquire tokens, raising if unavailable."""
        if not self.acquire(tokens, timeout=0.0):
            raise RateLimitExceededError("Rate limit exceeded.")

    def reset(self) -> None:
        with self._lock:
            self._tokens = self._config.capacity
            self._last_update = time.monotonic()


class AsyncTokenBucket:
    """Asyncio-safe token bucket."""

    def __init__(self, config: BucketConfig) -> None:
        self._config = config
        self._tokens = config.capacity
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0, timeout: float | None = None) -> bool:
        deadline = time.monotonic() + timeout if timeout else None
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_update
                self._tokens = min(self._config.capacity, self._tokens + elapsed * self._config.rate)
                self._last_update = now

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True

            if deadline is None:
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            await asyncio.sleep(min(0.05, remaining))

    async def acquire_blocking(self, tokens: float = 1.0) -> None:
        if not await self.acquire(tokens, timeout=0.0):
            raise RateLimitExceededError("Rate limit exceeded.")

    async def reset(self) -> None:
        async with self._lock:
            self._tokens = self._config.capacity
            self._last_update = time.monotonic()


class RateLimiter:
    """Per-domain and global rate limiter."""

    def __init__(
        self,
        global_config: BucketConfig | None = None,
        domain_configs: Dict[str, BucketConfig] | None = None,
    ) -> None:
        self._global = TokenBucket(global_config) if global_config else None
        self._domains: Dict[str, TokenBucket] = {}
        if domain_configs:
            for domain, config in domain_configs.items():
                self._domains[domain] = TokenBucket(config)

    def acquire(self, domain: str, tokens: float = 1.0, timeout: float = 0.0) -> bool:
        if self._global and not self._global.acquire(tokens, timeout):
            return False
        bucket = self._domains.get(domain)
        if bucket and not bucket.acquire(tokens, timeout):
            return False
        return True

    def acquire_blocking(self, domain: str, tokens: float = 1.0) -> None:
        if not self.acquire(domain, tokens, timeout=0.0):
            raise RateLimitExceededError(f"Rate limit exceeded for domain '{domain}'.")

    def set_domain_config(self, domain: str, config: BucketConfig) -> None:
        self._domains[domain] = TokenBucket(config)

    def reset(self) -> None:
        if self._global:
            self._global.reset()
        for bucket in self._domains.values():
            bucket.reset()


class AsyncRateLimiter:
    """Async per-domain and global rate limiter."""

    def __init__(
        self,
        global_config: BucketConfig | None = None,
        domain_configs: Dict[str, BucketConfig] | None = None,
    ) -> None:
        self._global = AsyncTokenBucket(global_config) if global_config else None
        self._domains: Dict[str, AsyncTokenBucket] = {}
        if domain_configs:
            for domain, config in domain_configs.items():
                self._domains[domain] = AsyncTokenBucket(config)

    async def acquire(self, domain: str, tokens: float = 1.0, timeout: float = 0.0) -> bool:
        if self._global and not await self._global.acquire(tokens, timeout):
            return False
        bucket = self._domains.get(domain)
        if bucket and not await bucket.acquire(tokens, timeout):
            return False
        return True

    async def acquire_blocking(self, domain: str, tokens: float = 1.0) -> None:
        if not await self.acquire(domain, tokens, timeout=0.0):
            raise RateLimitExceededError(f"Rate limit exceeded for domain '{domain}'.")

    def set_domain_config(self, domain: str, config: BucketConfig) -> None:
        self._domains[domain] = AsyncTokenBucket(config)

    async def reset(self) -> None:
        if self._global:
            await self._global.reset()
        for bucket in self._domains.values():
            await bucket.reset()
