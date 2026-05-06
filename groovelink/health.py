"""Health check monitor with degradation detection."""

from __future__ import annotations

import statistics
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List

from groovelink.exceptions import HealthCheckFailedError
from groovelink.utils import current_time


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthResult:
    status: HealthStatus
    response_time_ms: float
    timestamp: float = field(default_factory=current_time)
    message: str = ""


class HealthMonitor:
    """Monitor endpoint health and detect degradation."""

    def __init__(
        self,
        unhealthy_threshold: float = 5.0,
        degraded_threshold: float = 1.0,
        window_size: int = 10,
    ) -> None:
        self.unhealthy_threshold = unhealthy_threshold
        self.degraded_threshold = degraded_threshold
        self.window_size = window_size
        self._history: List[HealthResult] = []
        self._lock = threading.Lock()
        self._consecutive_failures = 0

    def record(self, response_time_ms: float, is_error: bool = False) -> HealthResult:
        """Record a response time and compute health status."""
        with self._lock:
            if is_error:
                self._consecutive_failures += 1
                status = (
                    HealthStatus.UNHEALTHY
                    if self._consecutive_failures >= 3
                    else HealthStatus.DEGRADED
                )
                result = HealthResult(
                    status=status,
                    response_time_ms=response_time_ms,
                    message=f"Error recorded (consecutive failures: {self._consecutive_failures})",
                )
            else:
                self._consecutive_failures = 0
                p95 = self._p95()
                if response_time_ms > self.unhealthy_threshold * 1000:
                    status = HealthStatus.UNHEALTHY
                    message = f"Response time {response_time_ms:.0f}ms exceeds unhealthy threshold."
                elif response_time_ms > self.degraded_threshold * 1000:
                    status = HealthStatus.DEGRADED
                    message = f"Response time {response_time_ms:.0f}ms exceeds degraded threshold."
                elif p95 is not None and p95 > self.degraded_threshold * 1000:
                    status = HealthStatus.DEGRADED
                    message = f"P95 latency elevated ({p95:.0f}ms)."
                else:
                    status = HealthStatus.HEALTHY
                    message = "Healthy."
                result = HealthResult(
                    status=status,
                    response_time_ms=response_time_ms,
                    message=message,
                )

            self._history.append(result)
            if len(self._history) > self.window_size:
                self._history.pop(0)
            return result

    def _p95(self) -> float | None:
        if not self._history:
            return None
        times = [r.response_time_ms for r in self._history]
        times.sort()
        idx = int(len(times) * 0.95)
        return times[min(idx, len(times) - 1)]

    def current_status(self) -> HealthStatus:
        with self._lock:
            if not self._history:
                return HealthStatus.HEALTHY
            return self._history[-1].status

    def summary(self) -> dict:
        with self._lock:
            if not self._history:
                return {"status": HealthStatus.HEALTHY.value, "samples": 0}
            times = [r.response_time_ms for r in self._history]
            return {
                "status": self._history[-1].status.value,
                "samples": len(self._history),
                "avg_ms": statistics.mean(times) if times else 0.0,
                "max_ms": max(times) if times else 0.0,
                "min_ms": min(times) if times else 0.0,
            }

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._consecutive_failures = 0

    def check(
        self,
        probe: Callable[[], tuple[float, bool]],
    ) -> HealthResult:
        """Run a health probe and record the result."""
        start = current_time()
        try:
            response_time_ms, is_error = probe()
        except Exception as exc:
            response_time_ms = (current_time() - start) * 1000
            is_error = True
        return self.record(response_time_ms, is_error)
