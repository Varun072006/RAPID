"""
Prometheus metrics + OpenTelemetry instrumentation for RAPID.

Metrics exposed at GET /metrics (Prometheus scrape endpoint).
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Counters ────────────────────────────────────────────────────
webhooks_received = Counter(
    "rapid_webhooks_received_total",
    "Total Razorpay webhook events received",
    ["event_type"],
)

webhooks_deduplicated = Counter(
    "rapid_webhooks_deduplicated_total",
    "Duplicate webhook events suppressed",
)

recovery_decisions = Counter(
    "rapid_recovery_decisions_total",
    "Recovery decisions made",
    ["action", "authorized"],
)

recovery_executions = Counter(
    "rapid_recovery_executions_total",
    "Recovery actions executed",
    ["action", "success"],
)

policy_violations = Counter(
    "rapid_policy_violations_total",
    "Policy engine denials",
    ["rule"],
)

reconciliation_performed = Counter(
    "rapid_reconciliation_total",
    "Unknown-state reconciliation queries",
    ["outcome"],
)

# ── Histograms ─────────────────────────────────────────────────
decision_latency = Histogram(
    "rapid_decision_latency_seconds",
    "Time to produce a recovery decision",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

# ── Gauges ────────────────────────────────────────────────────
recovered_amount_total = Gauge(
    "rapid_recovered_amount_total_paise",
    "Total payment amount recovered (in paise)",
)

active_unknown_payments = Gauge(
    "rapid_active_unknown_payments",
    "Payments currently in UNKNOWN state awaiting reconciliation",
)

system_failure_rate = Gauge(
    "rapid_system_failure_rate",
    "Current sliding-window payment failure rate",
)
