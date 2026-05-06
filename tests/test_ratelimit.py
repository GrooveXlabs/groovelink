"""Tests for rate limiting."""

from __future__ import annotations

import threading
import time

import pytest

from groovelink.exceptions import RateLimitExceededError
from groovelink.ratelimit import AsyncRateLimiter, BucketConfig, RateLimiter, TokenBucket


def test_token_bucket_acquires_tokens() -> None:
    bucket = TokenBucket(BucketConfig(rate=10.0, capacity=2.0))
    assert bucket.acquire(1.0, timeout=0.0)
    assert bucket.acquire(1.0, timeout=0.0)
    assert not bucket.acquire(1.0, timeout=0.0)


def test_token_bucket_refills_over_time() -> None:
    bucket = TokenBucket(BucketConfig(rate=100.0, capacity=1.0))
    assert bucket.acquire(1.0, timeout=0.0)
    assert not bucket.acquire(1.0, timeout=0.0)
    time.sleep(0.02)
    assert bucket.acquire(1.0, timeout=0.0)


def test_token_bucket_blocking_raises() -> None:
    bucket = TokenBucket(BucketConfig(rate=1.0, capacity=1.0))
    bucket.acquire_blocking(1.0)
    with pytest.raises(RateLimitExceededError):
        bucket.acquire_blocking(1.0)


def test_rate_limiter_per_domain() -> None:
    limiter = RateLimiter(
        domain_configs={"example.com": BucketConfig(rate=10.0, capacity=1.0)}
    )
    assert limiter.acquire("example.com", timeout=0.0)
    assert not limiter.acquire("example.com", timeout=0.0)
    assert limiter.acquire("other.com", timeout=0.0)


def test_rate_limiter_global_blocks() -> None:
    limiter = RateLimiter(global_config=BucketConfig(rate=10.0, capacity=1.0))
    assert limiter.acquire("any.com", timeout=0.0)
    assert not limiter.acquire("any.com", timeout=0.0)


def test_rate_limiter_concurrent() -> None:
    limiter = RateLimiter(
        global_config=BucketConfig(rate=0.0, capacity=5.0)
    )
    successes = []
    lock = threading.Lock()
    barrier = threading.Barrier(10)

    def worker() -> None:
        barrier.wait()  # Synchronize all threads
        ok = limiter.acquire("test.com", timeout=0.0)
        with lock:
            successes.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Exactly capacity=5 should succeed when all 10 race simultaneously
    assert sum(successes) == 5


@pytest.mark.asyncio
async def test_async_rate_limiter() -> None:
    limiter = AsyncRateLimiter(
        global_config=BucketConfig(rate=10.0, capacity=2.0)
    )
    assert await limiter.acquire("x.com", timeout=0.0)
    assert await limiter.acquire("x.com", timeout=0.0)
    assert not await limiter.acquire("x.com", timeout=0.0)


@pytest.mark.asyncio
async def test_async_token_bucket_blocking() -> None:
    bucket = TokenBucket(BucketConfig(rate=1.0, capacity=1.0))
    bucket.acquire_blocking(1.0)
    with pytest.raises(RateLimitExceededError):
        bucket.acquire_blocking(1.0)
