"""Custom exceptions for GrooveLink."""

from __future__ import annotations


class GrooveLinkError(Exception):
    """Base exception for all GrooveLink errors."""

    pass


class CircuitBreakerOpenError(GrooveLinkError):
    """Raised when the circuit breaker is OPEN and a request is attempted."""

    pass


class RetryExhaustedError(GrooveLinkError):
    """Raised when all retry attempts have been exhausted."""

    pass


class RateLimitExceededError(GrooveLinkError):
    """Raised when the rate limit has been exceeded."""

    pass


class ValidationError(GrooveLinkError):
    """Raised when input validation fails."""

    pass


class ServerError(GrooveLinkError):
    """Raised when an HTTP 5xx response is received."""

    pass


class HealthCheckFailedError(GrooveLinkError):
    """Raised when a health check fails critically."""

    pass
