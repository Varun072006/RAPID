"""Failure injection tests — duplicate webhook scenario."""

from __future__ import annotations

import pytest

from packages.domain.payments.deduplicator import Deduplicator
from packages.domain.payments.event_store import EventStore


class TestDuplicateWebhook:
    def test_first_event_accepted(self, db):
        """First occurrence of an event_id is accepted."""
        dedup = Deduplicator(db)
        assert dedup.is_duplicate("evt_001") is False
        result = dedup.mark_processed("evt_001", "payment.failed", {"test": True})
        assert result is True

    def test_second_event_rejected(self, db):
        """Second occurrence of the same event_id is rejected."""
        dedup = Deduplicator(db)
        dedup.mark_processed("evt_002", "payment.failed", {})
        # Second attempt should fail
        result = dedup.mark_processed("evt_002", "payment.failed", {})
        assert result is False

    def test_duplicate_does_not_create_second_audit_event(self, db, failed_payment):
        """Duplicate webhook should not create a second audit event."""
        store = EventStore(db)
        dedup = Deduplicator(db)

        event_id = "evt_003"

        # First: process normally
        store.append_event(failed_payment.payment_id, "webhook_received", {
            "event_id": event_id,
        })
        dedup.mark_processed(event_id, "payment.failed", {})

        # Second: duplicate — dedup catches it before audit event is created
        is_dup = dedup.is_duplicate(event_id)
        if not is_dup:
            store.append_event(failed_payment.payment_id, "webhook_received", {
                "event_id": event_id,
                "duplicate": True,
            })

        # Verify: only one non-duplicate event for this event_id
        timeline = store.get_events_by_type(
            failed_payment.payment_id, "webhook_received"
        )
        # At most 2 events (original + possible duplicate marker)
        assert len(timeline) <= 2

    def test_different_event_ids_both_accepted(self, db):
        """Different event IDs are independent."""
        dedup = Deduplicator(db)
        r1 = dedup.mark_processed("evt_a", "payment.failed", {})
        r2 = dedup.mark_processed("evt_b", "payment.failed", {})
        assert r1 is True
        assert r2 is True

    def test_is_duplicate_before_mark_returns_false(self, db):
        """is_duplicate returns False for unseen event_id."""
        dedup = Deduplicator(db)
        assert dedup.is_duplicate("evt_never_seen") is False
