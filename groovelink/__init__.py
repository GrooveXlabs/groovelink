"""GrooveLink — a resilient API client with circuit breaker, retry, rate limiting, and health checks."""

from groovelink.client import GrooveLinkClient, GrooveLinkSync
from groovelink.exceptions import (
    CircuitBreakerOpenError,
    GrooveLinkError,
    HealthCheckFailedError,
    RateLimitExceededError,
    RetryExhaustedError,
    ValidationError,
)

__all__ = [
    "GrooveLinkClient",
    "GrooveLinkSync",
    "GrooveLinkError",
    "CircuitBreakerOpenError",
    "RetryExhaustedError",
    "RateLimitExceededError",
    "ValidationError",
    "HealthCheckFailedError",
]

__version__ = "0.1.0"
