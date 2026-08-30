"""
Append-only event store — the single source of truth for payment history.

Design principles:
- Events are never mutated or deleted.
- get_timeline() is always available for full replay.
- append_event() is the only write operation.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from packages.domain.events.events import PaymentEvent
from packages.domain.payments.models import AuditEvent


class EventStore:
    """
    Append-only event store backed by the audit_events table.

    Every meaningful action in the system produces an event here:
    webhook arrival, state changes, ML classifications, decisions,
    policy checks, execution results, reconciliation outcomes.

    This enables:
    - Full timeline reconstruction for any payment
    - Debugging and post-mortem analysis
    - Replay-based testing
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def append_event(
        self,
        payment_id: str,
        event_type: str,
        data: dict[str, Any],
        actor: str = "system",
    ) -> PaymentEvent:
        """
        Record an event (append-only).

        Args:
            payment_id: Payment this event belongs to.
            event_type: Event category (e.g. state_changed, decision, execution).
            data:       Structured event payload.
            actor:      Who/what triggered this event.

        Returns:
            The persisted PaymentEvent.
        """
        audit_row = AuditEvent(
            payment_id=payment_id,
            event_type=event_type,
            details=data,
            actor=actor,
        )
        self.db.add(audit_row)
        self.db.commit()
        self.db.refresh(audit_row)

        event = PaymentEvent(
            event_id=str(audit_row.id),
            payment_id=payment_id,
            event_type=event_type,
            timestamp=audit_row.timestamp,
            data=data,
        )

        logger.debug(
            f"Event appended: payment={payment_id} type={event_type} actor={actor}"
        )
        return event

    def get_timeline(self, payment_id: str) -> list[PaymentEvent]:
        """
        Retrieve the full event timeline for a payment, in chronological order.

        Returns an empty list if no events exist (payment not found).
        """
        rows = (
            self.db.query(AuditEvent)
            .filter(AuditEvent.payment_id == payment_id)
            .order_by(AuditEvent.timestamp)
            .all()
        )

        return [
            PaymentEvent(
                event_id=str(row.id),
                payment_id=row.payment_id,
                event_type=row.event_type,
                timestamp=row.timestamp,
                data=row.details or {},
            )
            for row in rows
        ]

    def get_events_by_type(
        self, payment_id: str, event_type: str
    ) -> list[PaymentEvent]:
        """Filter timeline to a specific event type."""
        return [
            e for e in self.get_timeline(payment_id) if e.event_type == event_type
        ]
