"""Tests for retry strategies."""

from __future__ import annotations

import pytest

from groovelink.exceptions import RetryExhaustedError
from groovelink.retry import RetryConfig, RetryController, RetryStrategy


def flaky_function(fail_count: int) -> int:
    """Fail N times then succeed."""
    flaky_function.calls += 1  # type: ignore[attr-defined]
    if flaky_function.calls <= fail_count:
        raise ConnectionError("fail")
    return flaky_function.calls


flaky_function.calls = 0  # type: ignore[attr-defined]


def test_retry_success_on_first_attempt() -> None:
    flaky_function.calls = 0  # type: ignore[attr-defined]
    config = RetryConfig(max_retries=3)
    controller = RetryController(config)
    result = controller.execute(flaky_function, 0)
    assert result == 1


def test_retry_exhausted_raises() -> None:
    config = RetryConfig(max_retries=2, base_delay=0.01)
    controller = RetryController(config)
    with pytest.raises(RetryExhaustedError):
        controller.execute(lambda: (_ for _ in ()).throw(ConnectionError("always fail")))


def test_retry_succeeds_after_failures() -> None:
    flaky_function.calls = 0  # type: ignore[attr-defined]
    config = RetryConfig(max_retries=3, base_delay=0.01)
    controller = RetryController(config)
    result = controller.execute(flaky_function, 2)
    assert result == 3


def test_exponential_delay_with_jitter() -> None:
    config = RetryConfig(strategy=RetryStrategy.EXPONENTIAL, base_delay=1.0, jitter=True)
    delay = config.get_delay(2)
    assert delay >= 0
    assert delay <= 4.0


def test_linear_delay() -> None:
    config = RetryConfig(strategy=RetryStrategy.LINEAR, base_delay=1.0, max_delay=10.0)
    assert config.get_delay(0) == 1.0
    assert config.get_delay(1) == 2.0
    assert config.get_delay(2) == 3.0


def test_fixed_delay() -> None:
    config = RetryConfig(strategy=RetryStrategy.FIXED, base_delay=2.5)
    assert config.get_delay(5) == 2.5


@pytest.mark.asyncio
async def test_async_retry_success() -> None:
    flaky_function.calls = 0  # type: ignore[attr-defined]
    config = RetryConfig(max_retries=3, base_delay=0.01)
    controller = RetryController(config)
    result = await controller.execute_async(flaky_function, 2)
    assert result == 3


@pytest.mark.asyncio
async def test_async_retry_exhausted() -> None:
    config = RetryConfig(max_retries=1, base_delay=0.01)
    controller = RetryController(config)

    async def always_fail() -> None:
        raise ConnectionError("fail")

    with pytest.raises(RetryExhaustedError):
        await controller.execute_async(always_fail)
