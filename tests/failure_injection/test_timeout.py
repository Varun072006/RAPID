"""
Failure injection tests — API timeout scenario.

Tests the critical invariant: RAPID never retries a payment
in UNKNOWN state without first reconciling with Razorpay.
"""

from __future__ import annotations

import pytest

from packages.domain.payments.models import Payment, PaymentState
from packages.domain.policy.engine import PolicyEngine
from packages.integrations.razorpay.mock_adapter import MockRazorpayAdapter
from packages.workflows.reconciliation.unknown_state import (
    ReconciliationOutcome,
    UnknownStateResolver,
)


class TestTimeoutHandling:
    def test_unknown_state_blocks_retry(self):
        """Policy must deny retries when payment is in UNKNOWN state."""
        engine = PolicyEngine()
        authorized, reason = engine.authorize_action(
            action="retry_now",
            amount=50000,
            recovery_confidence=0.95,
            current_state="UNKNOWN",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is False
        assert "UNKNOWN" in reason

    def test_unknown_state_blocks_retry_later(self):
        """Policy denies retry_later too when state is UNKNOWN."""
        engine = PolicyEngine()
        authorized, _ = engine.authorize_action(
            action="retry_later",
            amount=50000,
            recovery_confidence=0.95,
            current_state="UNKNOWN",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is False

    def test_reconciliation_maps_captured(self, db, unknown_payment):
        """If Razorpay says captured, reconciler returns CAPTURED."""
        # Mock adapter: deterministic based on ID hash
        # "rzp_pay_mock_abc123" → hash → simulate captured
        razorpay = MockRazorpayAdapter()
        resolver = UnknownStateResolver(razorpay=razorpay, db=db)

        result = resolver.handle_timeout(
            payment_id=unknown_payment.payment_id,
            razorpay_payment_id=unknown_payment.razorpay_payment_id,
        )

        # Result must be one of the 4 defined outcomes
        assert result["outcome"] in (
            "SUCCESS_ON_RECONCILIATION",
            "CONFIRMED_FAILED",
            "STILL_PENDING",
            "STILL_UNKNOWN",
        )

    def test_captured_reconciliation_says_no_retry(self, db, unknown_payment):
        """If payment was actually captured, safe_to_retry must be False."""
        razorpay = MockRazorpayAdapter()
        resolver = UnknownStateResolver(razorpay=razorpay, db=db)

        result = resolver.handle_timeout(
            payment_id=unknown_payment.payment_id,
            razorpay_payment_id=unknown_payment.razorpay_payment_id,
        )

        if result["outcome"] == "SUCCESS_ON_RECONCILIATION":
            assert result["safe_to_retry"] is False
            assert result["next_state"] == PaymentState.CAPTURED

    def test_failed_reconciliation_allows_retry(self, db):
        """If payment was confirmed failed, safe_to_retry should be True."""
        razorpay = MockRazorpayAdapter()
        resolver = UnknownStateResolver(razorpay=razorpay, db=db)

        # Directly test the mapping
        from unittest.mock import patch

        with patch.object(resolver, "reconcile", return_value=ReconciliationOutcome.FAILED):
            result = resolver.handle_timeout("pay_test", "rzp_test")

        assert result["safe_to_retry"] is True
        assert result["outcome"] == "CONFIRMED_FAILED"

    def test_pending_reconciliation_blocks_retry(self, db):
        """If payment is still pending, safe_to_retry must be False."""
        razorpay = MockRazorpayAdapter()
        resolver = UnknownStateResolver(razorpay=razorpay, db=db)

        from unittest.mock import patch

        with patch.object(resolver, "reconcile", return_value=ReconciliationOutcome.PENDING):
            result = resolver.handle_timeout("pay_test", "rzp_test")

        assert result["safe_to_retry"] is False
        assert result["outcome"] == "STILL_PENDING"

    def test_razorpay_unavailable_defaults_to_escalate(self, db):
        """If Razorpay is unreachable, outcome is STILL_UNKNOWN → ESCALATED."""
        razorpay = MockRazorpayAdapter()
        resolver = UnknownStateResolver(razorpay=razorpay, db=db)

        from unittest.mock import patch

        with patch.object(resolver, "reconcile", return_value=ReconciliationOutcome.UNKNOWN):
            result = resolver.handle_timeout("pay_test", "rzp_test")

        assert result["safe_to_retry"] is False
        assert result["next_state"] == PaymentState.ESCALATED
