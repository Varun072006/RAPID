"""
Audit logger — thin wrapper that records every system action.

Every meaningful event in RAPID's lifecycle is recorded here:
- webhook_received
- state_changed
- failure_classified
- recovery_predicted
- action_selected
- policy_checked
- action_executed
- reconciliation_performed
- outcome_verified

Full timeline replay is always available for any payment.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from packages.domain.payments.event_store import EventStore


class AuditLogger:
    """
    Records every decision and action for full audit trail.

    This enables:
    - Post-mortem debugging of any payment
    - Replay-based testing
    - Compliance / audit reporting
    - Model explanation traceability
    """

    def __init__(self, db: Session) -> None:
        self._store = EventStore(db)

    def log(
        self,
        payment_id: str,
        event_type: str,
        details: dict[str, Any],
        actor: str = "system",
    ) -> None:
        """Record an event to the audit log."""
        self._store.append_event(payment_id, event_type, details, actor)

    def webhook_received(self, payment_id: str, event_id: str, event_type: str) -> None:
        self.log(
            payment_id,
            "webhook_received",
            {
                "razorpay_event_id": event_id,
                "event_type": event_type,
            },
            actor="razorpay_webhook",
        )

    def state_changed(
        self, payment_id: str, from_state: str, to_state: str, reason: str = ""
    ) -> None:
        self.log(
            payment_id,
            "state_changed",
            {
                "from": from_state,
                "to": to_state,
                "reason": reason,
            },
            actor="state_machine",
        )

    def failure_classified(self, payment_id: str, failure_mode: str, confidence: float) -> None:
        self.log(
            payment_id,
            "failure_classified",
            {
                "failure_mode": failure_mode,
                "confidence": confidence,
            },
            actor="ml_model",
        )

    def recovery_predicted(self, payment_id: str, predictions: dict[str, float]) -> None:
        self.log(
            payment_id,
            "recovery_predicted",
            {
                "predictions": predictions,
            },
            actor="ml_model",
        )

    def action_selected(
        self,
        payment_id: str,
        action: str,
        expected_value: float,
        all_evaluations: list[dict],
    ) -> None:
        self.log(
            payment_id,
            "action_selected",
            {
                "action": action,
                "expected_value_paise": expected_value,
                "all_evaluations": all_evaluations,
            },
            actor="revenue_optimizer",
        )

    def policy_checked(
        self,
        payment_id: str,
        action: str,
        authorized: bool,
        reason: str,
    ) -> None:
        self.log(
            payment_id,
            "policy_checked",
            {
                "action": action,
                "authorized": authorized,
                "reason": reason,
            },
            actor="policy_engine",
        )

    def action_executed(
        self,
        payment_id: str,
        action: str,
        idempotency_key: str,
        result: dict,
    ) -> None:
        self.log(
            payment_id,
            "action_executed",
            {
                "action": action,
                "idempotency_key": idempotency_key,
                "result": result,
            },
            actor="orchestrator",
        )

    def reconciliation_performed(
        self,
        payment_id: str,
        outcome: str,
        safe_to_retry: bool,
        next_state: str,
    ) -> None:
        self.log(
            payment_id,
            "reconciliation_performed",
            {
                "outcome": outcome,
                "safe_to_retry": safe_to_retry,
                "next_state": next_state,
            },
            actor="reconciler",
        )

    def get_timeline(self, payment_id: str) -> list[dict]:
        """Return full audit timeline as a list of dicts (for API/dashboard)."""
        events = self._store.get_timeline(payment_id)
        return [
            {
                "event_id": e.event_id,
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "actor": e.data.get("actor", "system"),
                "details": e.data,
            }
            for e in events
        ]
