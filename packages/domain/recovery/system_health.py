"""
System health detector — detects payment system degradation in real time.

Uses a sliding window over recent payment outcomes to compute failure rate.
When failure rate crosses a threshold, the system transitions to DEGRADED
or INCIDENT state, which pauses automatic retries.

This prevents RAPID from hammering a degraded bank/network with retries
that are unlikely to succeed — saving costs and avoiding rate limits.
"""

from __future__ import annotations

import enum
from collections import deque

from loguru import logger


class SystemHealth(str, enum.Enum):
    """Current system health assessment."""

    HEALTHY = "HEALTHY"     # < 5% failure rate — normal operation
    DEGRADED = "DEGRADED"   # 5–15% failure rate — monitor closely
    INCIDENT = "INCIDENT"   # > 15% failure rate — pause retries


# Thresholds (configurable)
HEALTHY_THRESHOLD = 0.05
INCIDENT_THRESHOLD = 0.15


class HealthDetector:
    """
    Sliding-window failure rate monitor.

    Maintains a fixed-size deque of recent payment outcomes (True=success,
    False=failure). Failure rate = failures / window_size.

    Thread safety: deque operations are atomic in CPython for single items.
    For production use, replace with Redis-backed sliding window.
    """

    def __init__(self, window_size: int = 100) -> None:
        self.window_size = window_size
        self._outcomes: deque[bool] = deque(maxlen=window_size)

    def record_outcome(self, success: bool) -> None:
        """Record a payment outcome (True=success, False=failure)."""
        self._outcomes.append(success)

    def failure_rate(self) -> float:
        """Current failure rate in the sliding window."""
        if not self._outcomes:
            return 0.0
        failures = sum(1 for o in self._outcomes if not o)
        return failures / len(self._outcomes)

    def health(self) -> SystemHealth:
        """Current system health assessment."""
        rate = self.failure_rate()
        if rate < HEALTHY_THRESHOLD:
            return SystemHealth.HEALTHY
        elif rate < INCIDENT_THRESHOLD:
            return SystemHealth.DEGRADED
        else:
            return SystemHealth.INCIDENT

    def should_pause_retries(self) -> bool:
        """
        Should automatic retries be paused?

        Always True during INCIDENT. False otherwise.
        (DEGRADED still allows retries but triggers alerts.)
        """
        h = self.health()
        if h == SystemHealth.INCIDENT:
            logger.warning(
                f"System INCIDENT: failure_rate={self.failure_rate():.1%} "
                f"— automatic retries PAUSED"
            )
            return True
        return False

    def status_summary(self) -> dict:
        """Serializable status for API/dashboard."""
        rate = self.failure_rate()
        h = self.health()
        return {
            "health": h.value,
            "failure_rate": round(rate, 4),
            "window_size": self.window_size,
            "samples_collected": len(self._outcomes),
            "retries_paused": h == SystemHealth.INCIDENT,
        }
