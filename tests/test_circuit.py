"""Tests for circuit breaker."""

from __future__ import annotations

import tempfile

import pytest

from groovelink.circuit import CircuitBreaker, CircuitState
from groovelink.exceptions import CircuitBreakerOpenError


def dummy_success() -> str:
    return "ok"


def dummy_failure() -> None:
    raise RuntimeError("fail")


def test_circuit_closed_by_default() -> None:
    cb = CircuitBreaker("test", failure_threshold=3)
    assert cb.state == CircuitState.CLOSED


def test_circuit_opens_after_threshold() -> None:
    cb = CircuitBreaker("test", failure_threshold=3)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.call(dummy_failure)
    assert cb.state == CircuitState.OPEN
    with pytest.raises(CircuitBreakerOpenError):
        cb.call(dummy_success)


def test_circuit_half_open_then_closes() -> None:
    cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(dummy_failure)
    assert cb.state == CircuitState.OPEN
    import time

    time.sleep(0.15)
    cb.call(dummy_success)
    cb.call(dummy_success)
    cb.call(dummy_success)
    assert cb.state == CircuitState.CLOSED


def test_circuit_half_open_then_reopens() -> None:
    cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(dummy_failure)
    assert cb.state == CircuitState.OPEN
    import time

    time.sleep(0.15)
    with pytest.raises(RuntimeError):
        cb.call(dummy_failure)
    assert cb.state == CircuitState.OPEN


def test_circuit_state_persistence() -> None:
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=10, state_file=path)
    with pytest.raises(RuntimeError):
        cb.call(dummy_failure)
    assert cb.state == CircuitState.OPEN

    cb2 = CircuitBreaker("test", failure_threshold=1, recovery_timeout=10, state_file=path)
    assert cb2.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_async_call_success() -> None:
    cb = CircuitBreaker("test")
    result = await cb.call_async(dummy_success)
    assert result == "ok"


@pytest.mark.asyncio
async def test_async_call_failure_opens() -> None:
    cb = CircuitBreaker("test", failure_threshold=2)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call_async(dummy_failure)
    assert cb.state == CircuitState.OPEN
