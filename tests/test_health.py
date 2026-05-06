"""Tests for health monitor."""

from __future__ import annotations

from groovelink.health import HealthMonitor, HealthStatus


def test_health_healthy() -> None:
    monitor = HealthMonitor(unhealthy_threshold=5.0, degraded_threshold=1.0)
    result = monitor.record(response_time_ms=200.0, is_error=False)
    assert result.status == HealthStatus.HEALTHY


def test_health_degraded_by_latency() -> None:
    monitor = HealthMonitor(unhealthy_threshold=5.0, degraded_threshold=1.0)
    result = monitor.record(response_time_ms=1500.0, is_error=False)
    assert result.status == HealthStatus.DEGRADED


def test_health_unhealthy_by_latency() -> None:
    monitor = HealthMonitor(unhealthy_threshold=5.0, degraded_threshold=1.0)
    result = monitor.record(response_time_ms=6000.0, is_error=False)
    assert result.status == HealthStatus.UNHEALTHY


def test_health_degraded_by_error() -> None:
    monitor = HealthMonitor()
    result = monitor.record(response_time_ms=100.0, is_error=True)
    assert result.status == HealthStatus.DEGRADED


def test_health_unhealthy_after_consecutive_errors() -> None:
    monitor = HealthMonitor()
    for _ in range(2):
        monitor.record(response_time_ms=100.0, is_error=True)
    result = monitor.record(response_time_ms=100.0, is_error=True)
    assert result.status == HealthStatus.UNHEALTHY


def test_health_summary() -> None:
    monitor = HealthMonitor()
    monitor.record(100.0, is_error=False)
    monitor.record(200.0, is_error=False)
    summary = monitor.summary()
    assert summary["status"] == HealthStatus.HEALTHY.value
    assert summary["samples"] == 2
    assert summary["avg_ms"] == 150.0


def test_health_check_with_probe() -> None:
    monitor = HealthMonitor()

    def probe() -> tuple[float, bool]:
        return (250.0, False)

    result = monitor.check(probe)
    assert result.status == HealthStatus.HEALTHY
    assert result.response_time_ms == 250.0


def test_health_check_probe_exception() -> None:
    monitor = HealthMonitor()

    def probe() -> tuple[float, bool]:
        raise RuntimeError("boom")

    result = monitor.check(probe)
    assert result.status == HealthStatus.DEGRADED
