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

    HEALTHY = "HEALTHY"  # < 5% failure rate — normal operation
    DEGRADED = "DEGRADED"  # 5–15% failure rate — monitor closely
    INCIDENT = "INCIDENT"  # > 15% failure rate — pause retries


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
        self._segment_outcomes: dict[tuple[str, str], deque[bool]] = {}

    def record_outcome(self, success: bool, bank: str = "default", method: str = "default") -> None:
        """Record a payment outcome (True=success, False=failure)."""
        self._outcomes.append(success)
        key = (str(bank), str(method))
        if key not in self._segment_outcomes:
            self._segment_outcomes[key] = deque(maxlen=self.window_size)
        self._segment_outcomes[key].append(success)

    def failure_rate(self, bank: str | None = None, method: str | None = None) -> float:
        """Current failure rate in the global or segmented window."""
        if bank is not None and method is not None:
            key = (str(bank), str(method))
            dq = self._segment_outcomes.get(key)
            if not dq:
                return 0.0
            failures = sum(1 for o in dq if not o)
            return failures / len(dq)

        if not self._outcomes:
            return 0.0
        failures = sum(1 for o in self._outcomes if not o)
        return failures / len(self._outcomes)

    def health(self, bank: str | None = None, method: str | None = None) -> SystemHealth:
        """Current system health assessment."""
        rate = self.failure_rate(bank, method)
        if rate < HEALTHY_THRESHOLD:
            return SystemHealth.HEALTHY
        elif rate < INCIDENT_THRESHOLD:
            return SystemHealth.DEGRADED
        else:
            return SystemHealth.INCIDENT

    def should_pause_retries(self, bank: str | None = None, method: str | None = None) -> bool:
        """
        Should automatic retries be paused?

        Returns True if global OR segment health is INCIDENT.
        """
        h = self.health(bank, method)
        global_h = self.health()
        if h == SystemHealth.INCIDENT or global_h == SystemHealth.INCIDENT:
            logger.warning(
                f"System INCIDENT detected: segment=({bank},{method}) "
                f"rate={self.failure_rate(bank, method):.1%} — retries PAUSED"
            )
            return True
        return False

    def status_summary(self) -> dict:
        """Serializable status for API/dashboard."""
        rate = self.failure_rate()
        h = self.health()
        segments_summary = {}
        for (b, m), dq in self._segment_outcomes.items():
            if len(dq) >= 5:  # Report segments with sufficient samples
                fail_cnt = sum(1 for x in dq if not x)
                segments_summary[f"{b}:{m}"] = round(fail_cnt / len(dq), 4)

        return {
            "health": h.value,
            "failure_rate": round(rate, 4),
            "window_size": self.window_size,
            "samples_collected": len(self._outcomes),
            "retries_paused": h == SystemHealth.INCIDENT,
            "segments": segments_summary,
        }
