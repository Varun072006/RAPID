"""
Payment semantic contract tests.

These tests verify that the system respects fundamental payment semantics:
- Captured payments are never retried (money already collected)
- Settled payments are truly terminal
- UNKNOWN state always blocks retry actions
- Policy violations are always zero when rules are followed

If any of these fail, the system has a serious correctness bug.
"""

from __future__ import annotations

import pytest

from packages.domain.payments.models import PaymentState
from packages.domain.payments.state_machine import StateMachine
from packages.domain.policy.engine import PolicyEngine


class TestPaymentSemantics:
    def test_captured_payment_never_transitions_to_failed(self):
        """Once payment is captured, it cannot go to failed."""
        success, _ = StateMachine.transition(PaymentState.CAPTURED, PaymentState.FAILED)
        assert success is False, "CAPTURED → FAILED would mean reversing a real money movement"

    def test_settled_payment_is_absolutely_final(self):
        """SETTLED has zero valid outgoing transitions."""
        for state in PaymentState:
            success, _ = StateMachine.transition(PaymentState.SETTLED, state)
            assert success is False, f"SETTLED → {state} must be impossible"

    def test_unknown_state_always_blocks_all_retry_variants(self):
        """Every retry-flavoured action is blocked in UNKNOWN state."""
        engine = PolicyEngine()
        retry_actions = ["retry_now", "retry_later"]
        for action in retry_actions:
            authorized, reason = engine.authorize_action(
                action=action,
                amount=100,
                recovery_confidence=1.0,  # even with perfect confidence
                current_state="UNKNOWN",
                retry_count=0,
                system_healthy=True,
            )
            assert authorized is False, (
                f"Action '{action}' in UNKNOWN state must always be denied. "
                f"Got: authorized={authorized}, reason={reason}"
            )

    def test_zero_policy_violations_under_valid_inputs(self):
        """
        Under all valid inputs (state != UNKNOWN, amount under limit,
        retries under cap, confidence above threshold, system healthy),
        policy must always authorize.
        """
        engine = PolicyEngine()
        authorized, reason = engine.authorize_action(
            action="payment_link",
            amount=100000,
            recovery_confidence=0.8,
            current_state="FAILED",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is True, f"Expected authorization. Got: {reason}"

    def test_payment_link_not_subject_to_retry_cap_or_system_health(self):
        """
        Payment links don't hammer the banking network.
        They should be allowed even during incidents and when retry cap is reached.
        """
        engine = PolicyEngine()
        # During incident
        authorized, _ = engine.authorize_action(
            action="payment_link",
            amount=50000,
            recovery_confidence=0.7,
            current_state="FAILED",
            retry_count=99,  # way over cap
            system_healthy=False,  # incident
        )
        assert authorized is True
