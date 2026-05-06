"""Main resilient API client for GrooveLink."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
from urllib.parse import urljoin

from groovelink.cache import ResponseCache
from groovelink.circuit import CircuitBreaker
from groovelink.exceptions import CircuitBreakerOpenError, RateLimitExceededError, ServerError, ValidationError
from groovelink.health import HealthMonitor, HealthResult
from groovelink.ratelimit import AsyncRateLimiter, BucketConfig, RateLimiter
from groovelink.retry import RetryConfig, RetryController, RetryStrategy
from groovelink.utils import HookRegistry, redact_headers
from groovelink.validators import sanitize_path, validate_url

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]


class _BaseClient:
    """Shared configuration and helpers."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        retries: int = 3,
        retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        circuit_threshold: int = 5,
        circuit_recovery: float = 30.0,
        rate_limit: float | None = None,
        rate_limit_per_domain: Dict[str, float] | None = None,
        cache_ttl: float = 300.0,
        hooks: HookRegistry | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.retry_strategy = retry_strategy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.circuit_threshold = circuit_threshold
        self.circuit_recovery = circuit_recovery
        self.rate_limit = rate_limit
        self.rate_limit_per_domain = rate_limit_per_domain or {}
        self.cache_ttl = cache_ttl
        self.hooks = hooks or HookRegistry()
        self.cache = ResponseCache(default_ttl=cache_ttl)
        self.health_monitor = HealthMonitor()

        validate_url(self.base_url)

        self.retry_config = RetryConfig(
            max_retries=retries,
            strategy=retry_strategy,
            base_delay=base_delay,
            max_delay=max_delay,
            retryable_exceptions=(ServerError, ConnectionError, TimeoutError),
        )
        self.retry_controller = RetryController(self.retry_config)

    def _build_url(self, path: str) -> str:
        safe_path = sanitize_path(path)
        return urljoin(self.base_url + "/", safe_path.lstrip("/"))

    def _make_domain(self, url: str) -> str:
        from urllib.parse import urlparse

        return urlparse(url).netloc

    def _prepare_headers(self, headers: Dict[str, str] | None) -> Dict[str, str]:
        default_headers = {
            "User-Agent": "GrooveLink/0.1.0",
            "Accept": "application/json",
        }
        if headers:
            default_headers.update(headers)
        return default_headers


class GrooveLinkClient(_BaseClient):
    """Async resilient HTTP client using httpx."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._client: Optional[Any] = None
        self._circuit = CircuitBreaker(
            name="groovelink_async",
            failure_threshold=self.circuit_threshold,
            recovery_timeout=self.circuit_recovery,
        )
        domain_configs: Dict[str, BucketConfig] = {}
        for domain, limit in self.rate_limit_per_domain.items():
            domain_configs[domain] = BucketConfig(rate=limit / 60.0, capacity=limit)
        global_config = None
        if self.rate_limit:
            global_config = BucketConfig(rate=self.rate_limit / 60.0, capacity=self.rate_limit)
        self._rate_limiter = AsyncRateLimiter(
            global_config=global_config,
            domain_configs=domain_configs,
        )

    async def __aenter__(self) -> GrooveLinkClient:
        if httpx is None:
            raise ImportError("httpx is required for the async client.")
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Perform an async HTTP request with resilience."""
        if httpx is None:
            raise ImportError("httpx is required for the async client.")
        if self._client is None:
            raise RuntimeError("Client not entered. Use 'async with' context manager.")

        url = self._build_url(path)
        validate_url(url)
        domain = self._make_domain(url)

        await self._rate_limiter.acquire_blocking(domain)

        headers = self._prepare_headers(kwargs.pop("headers", None))
        kwargs["headers"] = headers

        cache_key = f"{method}:{url}"

        async def _do_request() -> Any:
            start = asyncio.get_event_loop().time()
            try:
                response = await self._client.request(method, url, **kwargs)  # type: ignore[union-attr]
            except Exception as exc:
                elapsed = (asyncio.get_event_loop().time() - start) * 1000
                self.health_monitor.record(elapsed, is_error=True)
                self.hooks.emit("request_error", method, url, exc, redact_headers(headers))
                raise
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            is_error = response.status_code >= 500
            health = self.health_monitor.record(elapsed, is_error=is_error)
            self.hooks.emit("request_success", method, url, response.status_code, health.status.value)
            if is_error:
                raise ServerError(f"HTTP {response.status_code}")
            self.cache.set(cache_key, response, ttl=self.cache_ttl)
            return response

        try:
            return await self._circuit.call_async(
                self.retry_controller.execute_async, _do_request
            )
        except CircuitBreakerOpenError:
            cached = self.cache.get(cache_key)
            if cached is not None:
                self.hooks.emit("circuit_fallback", method, url, "cache_hit")
                return cached
            self.hooks.emit("circuit_fallback", method, url, "no_cache")
            raise
        except RateLimitExceededError:
            self.hooks.emit("rate_limited", method, url)
            raise

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> Any:
        return await self.request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Any:
        return await self.request("DELETE", path, **kwargs)

    async def health_check(self, path: str = "/") -> HealthResult:
        """Run a lightweight health probe."""
        start = asyncio.get_event_loop().time()
        try:
            response = await self.get(path)
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            is_error = response.status_code >= 500
        except Exception:
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            is_error = True
        return self.health_monitor.record(elapsed, is_error)


class GrooveLinkSync(_BaseClient):
    """Sync resilient HTTP client using requests."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._session: Optional[Any] = None
        self._circuit = CircuitBreaker(
            name="groovelink_sync",
            failure_threshold=self.circuit_threshold,
            recovery_timeout=self.circuit_recovery,
        )
        domain_configs: Dict[str, BucketConfig] = {}
        for domain, limit in self.rate_limit_per_domain.items():
            domain_configs[domain] = BucketConfig(rate=limit / 60.0, capacity=limit)
        global_config = None
        if self.rate_limit:
            global_config = BucketConfig(rate=self.rate_limit / 60.0, capacity=self.rate_limit)
        self._rate_limiter = RateLimiter(
            global_config=global_config,
            domain_configs=domain_configs,
        )

    def __enter__(self) -> GrooveLinkSync:
        if requests is None:
            raise ImportError("requests is required for the sync client.")
        self._session = requests.Session()
        return self

    def __exit__(self, *args: Any) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Perform a sync HTTP request with resilience."""
        if requests is None:
            raise ImportError("requests is required for the sync client.")
        if self._session is None:
            raise RuntimeError("Client not entered. Use 'with' context manager.")

        url = self._build_url(path)
        validate_url(url)
        domain = self._make_domain(url)

        self._rate_limiter.acquire_blocking(domain)

        headers = self._prepare_headers(kwargs.pop("headers", None))
        kwargs["headers"] = headers
        kwargs["timeout"] = self.timeout

        cache_key = f"{method}:{url}"

        import time as _time

        def _do_request() -> Any:
            start = _time.monotonic()
            try:
                response = self._session.request(method, url, **kwargs)  # type: ignore[union-attr]
            except Exception as exc:
                elapsed = (_time.monotonic() - start) * 1000
                self.health_monitor.record(elapsed, is_error=True)
                self.hooks.emit("request_error", method, url, exc, redact_headers(headers))
                raise
            elapsed = (_time.monotonic() - start) * 1000
            is_error = response.status_code >= 500
            health = self.health_monitor.record(elapsed, is_error=is_error)
            self.hooks.emit("request_success", method, url, response.status_code, health.status.value)
            if is_error:
                raise ServerError(f"HTTP {response.status_code}")
            self.cache.set(cache_key, response, ttl=self.cache_ttl)
            return response

        try:
            return self._circuit.call(
                self.retry_controller.execute, _do_request
            )
        except CircuitBreakerOpenError:
            cached = self.cache.get(cache_key)
            if cached is not None:
                self.hooks.emit("circuit_fallback", method, url, "cache_hit")
                return cached
            self.hooks.emit("circuit_fallback", method, url, "no_cache")
            raise
        except RateLimitExceededError:
            self.hooks.emit("rate_limited", method, url)
            raise

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)

    def health_check(self, path: str = "/") -> HealthResult:
        """Run a lightweight health probe."""
        import time as _time

        start = _time.monotonic()
        try:
            response = self.get(path)
            elapsed = (_time.monotonic() - start) * 1000
            is_error = response.status_code >= 500
        except Exception:
            elapsed = (_time.monotonic() - start) * 1000
            is_error = True
        return self.health_monitor.record(elapsed, is_error)
