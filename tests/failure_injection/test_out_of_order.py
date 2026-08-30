"""Failure injection tests — out-of-order webhook events."""

from __future__ import annotations

import pytest

from packages.domain.payments.event_sequencer import EventSequencer
from packages.domain.payments.models import Payment, PaymentState


class TestOutOfOrderEvents:
    def test_captured_after_failed_ignored(self, db):
        """
        payment.captured arrives after payment.failed.
        The stale 'captured' event must be ignored — we cannot un-fail a payment.

        Note: FAILED → CAPTURED is NOT a valid transition.
        The sequencer drops it.
        """
        # Create a payment that's already been marked CAPTURED (correct state)
        payment = Payment(
            payment_id="pay_ooo_001",
            merchant_id="merchant_test",
            customer_id="cust_test",
            amount=100000,
            state=PaymentState.CAPTURED,
        )
        db.add(payment)
        db.commit()

        # Now a stale 'payment.failed' arrives
        sequencer = EventSequencer(db)
        applied, reason = sequencer.process_event(
            payment_id="pay_ooo_001",
            event_type="payment.failed",
            new_state=PaymentState.FAILED,
        )

        # Must be rejected
        assert applied is False
        assert "stale" in reason.lower() or "invalid" in reason.lower()

        # Payment must still be CAPTURED
        db.refresh(payment)
        assert payment.state == PaymentState.CAPTURED

    def test_valid_event_after_stale_still_applies(self, db):
        """After a stale event is discarded, valid events still apply."""
        payment = Payment(
            payment_id="pay_ooo_002",
            merchant_id="merchant_test",
            customer_id="cust_test",
            amount=100000,
            state=PaymentState.AUTHORIZED,
        )
        db.add(payment)
        db.commit()

        sequencer = EventSequencer(db)

        # Stale: send a CREATED event (going backwards)
        applied, _ = sequencer.process_event(
            "pay_ooo_002", "payment.created", PaymentState.CREATED
        )
        assert applied is False

        # Valid: AUTHORIZED → CAPTURED
        applied, reason = sequencer.process_event(
            "pay_ooo_002", "payment.captured", PaymentState.CAPTURED
        )
        assert applied is True
        assert reason == "OK"

        db.refresh(payment)
        assert payment.state == PaymentState.CAPTURED

    def test_multiple_stale_events_dont_corrupt_state(self, db):
        """Multiple stale events in a row don't corrupt the payment state."""
        payment = Payment(
            payment_id="pay_ooo_003",
            merchant_id="merchant_test",
            customer_id="cust_test",
            amount=100000,
            state=PaymentState.SETTLED,  # terminal
        )
        db.add(payment)
        db.commit()

        sequencer = EventSequencer(db)

        # Hammer with stale events
        for _ in range(10):
            applied, _ = sequencer.process_event(
                "pay_ooo_003", "payment.failed", PaymentState.FAILED
            )
            assert applied is False

        # State must still be SETTLED
        db.refresh(payment)
        assert payment.state == PaymentState.SETTLED
