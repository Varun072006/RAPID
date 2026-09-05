"""
Webhook deduplicator — ensures idempotent event processing.

Razorpay guarantees at-least-once delivery: the same webhook event
may arrive multiple times (retries on 5xx, network issues, etc.).

Strategy: use the Razorpay-provided event_id as the deduplication key.
The database enforces uniqueness via a constraint — the application
layer never needs a distributed lock.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.domain.payments.models import WebhookReceivedEvent


class Deduplicator:
    """
    Idempotent webhook processing via database-level unique constraint.

    Usage:
        dedup = Deduplicator(db)
        if dedup.is_duplicate(event_id):
            return {"status": "deduplicated"}
        # ... process event ...
        dedup.mark_processed(event_id, event_type, raw_payload)
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def is_duplicate(self, event_id: str) -> bool:
        """
        Check whether this event_id has already been processed.

        Does NOT claim the event — call mark_processed() after
        successful processing.
        """
        existing = (
            self.db.query(WebhookReceivedEvent)
            .filter(WebhookReceivedEvent.event_id == event_id)
            .first()
        )
        return existing is not None

    def mark_processed(
        self,
        event_id: str,
        event_type: str,
        raw_payload: dict[str, Any],
    ) -> bool:
        """
        Atomically mark an event as processed.

        The database unique constraint on event_id means that even if
        two concurrent processes attempt to mark the same event, only
        one will succeed (the other gets IntegrityError).

        Returns:
            True  — first time processing, commit succeeded.
            False — already processed (IntegrityError caught), caller should skip.
        """
        row = WebhookReceivedEvent(
            event_id=event_id,
            event_type=event_type,
            raw_payload=raw_payload,
            processed=True,
        )
        try:
            self.db.add(row)
            self.db.commit()
            logger.debug(f"Webhook marked processed: {event_id} ({event_type})")
            return True
        except IntegrityError:
            self.db.rollback()
            logger.warning(f"Duplicate webhook detected and suppressed: {event_id}")
            return False
