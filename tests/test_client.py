"""Tests for GrooveLink clients."""

from __future__ import annotations

import pytest
import requests
import respx
import responses
from httpx import Response as HttpxResponse

from groovelink.client import GrooveLinkClient, GrooveLinkSync
from groovelink.exceptions import CircuitBreakerOpenError, RateLimitExceededError
from groovelink.health import HealthStatus


@responses.activate
def test_sync_client_get_success() -> None:
    responses.add(
        responses.GET,
        "https://api.example.com/users",
        json={"id": 1},
        status=200,
    )
    client = GrooveLinkSync(base_url="https://api.example.com", timeout=5)
    with client:
        response = client.get("/users")
        assert response.status_code == 200
        assert response.json() == {"id": 1}


@responses.activate
def test_sync_client_retry_on_500() -> None:
    responses.add(
        responses.GET,
        "https://api.example.com/broken",
        body="fail",
        status=500,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/broken",
        body="fail",
        status=500,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/broken",
        json={"ok": True},
        status=200,
    )
    client = GrooveLinkSync(
        base_url="https://api.example.com",
        timeout=5,
        retries=3,
        base_delay=0.01,
    )
    with client:
        response = client.get("/broken")
        assert response.status_code == 200


@responses.activate
def test_sync_client_circuit_opens_and_uses_cache() -> None:
    responses.add(
        responses.GET,
        "https://api.example.com/fail",
        body="cached",
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/fail",
        body="fail",
        status=500,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/fail",
        body="fail",
        status=500,
    )
    client = GrooveLinkSync(
        base_url="https://api.example.com",
        timeout=5,
        retries=0,
        circuit_threshold=2,
        base_delay=0.01,
    )
    with client:
        r1 = client.get("/fail")
        assert r1.status_code == 200
        # Now fail twice to open circuit
        with pytest.raises(Exception):
            client.get("/fail")
        with pytest.raises(Exception):
            client.get("/fail")
        # Circuit open, should return cached response
        r2 = client.get("/fail")
        assert r2.text == "cached"


@responses.activate
def test_sync_client_rate_limit() -> None:
    responses.add(
        responses.GET,
        "https://api.example.com/fast",
        json={},
        status=200,
    )
    client = GrooveLinkSync(
        base_url="https://api.example.com",
        timeout=5,
        rate_limit=1.0,
    )
    with client:
        client.get("/fast")
        with pytest.raises(RateLimitExceededError):
            client.get("/fast")


@respx.mock
@pytest.mark.asyncio
async def test_async_client_get_success() -> None:
    route = respx.get("https://api.example.com/users").mock(
        return_value=HttpxResponse(200, json={"id": 1})
    )
    client = GrooveLinkClient(base_url="https://api.example.com", timeout=5)
    async with client:
        response = await client.get("/users")
        assert response.status_code == 200
        assert response.json() == {"id": 1}
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_async_client_health_check() -> None:
    route = respx.get("https://api.example.com/health").mock(
        return_value=HttpxResponse(200)
    )
    client = GrooveLinkClient(base_url="https://api.example.com", timeout=5)
    async with client:
        result = await client.health_check("/health")
        assert result.status == HealthStatus.HEALTHY
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_async_client_circuit_opens() -> None:
    route = respx.get("https://api.example.com/down").mock(
        return_value=HttpxResponse(500)
    )
    client = GrooveLinkClient(
        base_url="https://api.example.com",
        timeout=5,
        retries=0,
        circuit_threshold=2,
    )
    async with client:
        with pytest.raises(Exception):
            await client.get("/down")
        with pytest.raises(Exception):
            await client.get("/down")
        with pytest.raises(CircuitBreakerOpenError):
            await client.get("/down")
    assert route.call_count == 2


def test_client_input_validation() -> None:
    with pytest.raises(Exception):
        GrooveLinkSync(base_url="ftp://evil.com")


def test_client_sanitizes_path() -> None:
    client = GrooveLinkSync(base_url="https://api.example.com")
    assert client._build_url("/../etc/passwd") == "https://api.example.com/etc/passwd"
