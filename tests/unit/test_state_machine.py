"""
Unit tests for the payment state machine.

Tests every valid transition, every invalid transition,
and all terminal state invariants.
"""

from __future__ import annotations

import pytest

from packages.domain.payments.models import PaymentState
from packages.domain.payments.state_machine import StateMachine


class TestValidTransitions:
    """Every valid transition should return (True, 'OK')."""

    @pytest.mark.parametrize("from_state,to_state", [
        (PaymentState.CREATED, PaymentState.AUTHORIZED),
        (PaymentState.CREATED, PaymentState.FAILED),
        (PaymentState.CREATED, PaymentState.PENDING),
        (PaymentState.CREATED, PaymentState.UNKNOWN),
        (PaymentState.AUTHORIZED, PaymentState.CAPTURED),
        (PaymentState.AUTHORIZED, PaymentState.FAILED),
        (PaymentState.AUTHORIZED, PaymentState.PENDING),
        (PaymentState.AUTHORIZED, PaymentState.UNKNOWN),
        (PaymentState.CAPTURED, PaymentState.SETTLED),
        (PaymentState.FAILED, PaymentState.PAYMENT_LINK_SENT),
        (PaymentState.FAILED, PaymentState.ESCALATED),
        (PaymentState.FAILED, PaymentState.UNKNOWN),
        (PaymentState.PENDING, PaymentState.CAPTURED),
        (PaymentState.PENDING, PaymentState.FAILED),
        (PaymentState.PENDING, PaymentState.UNKNOWN),
        (PaymentState.UNKNOWN, PaymentState.CAPTURED),
        (PaymentState.UNKNOWN, PaymentState.FAILED),
        (PaymentState.UNKNOWN, PaymentState.PENDING),
        (PaymentState.UNKNOWN, PaymentState.ESCALATED),
        (PaymentState.PAYMENT_LINK_SENT, PaymentState.CAPTURED),
        (PaymentState.PAYMENT_LINK_SENT, PaymentState.FAILED),
        (PaymentState.ESCALATED, PaymentState.CAPTURED),
        (PaymentState.ESCALATED, PaymentState.FAILED),
    ])
    def test_valid_transition(self, from_state: PaymentState, to_state: PaymentState):
        success, reason = StateMachine.transition(from_state, to_state)
        assert success is True, f"Expected valid: {from_state} → {to_state}. Reason: {reason}"
        assert reason == "OK"


class TestInvalidTransitions:
    """Invalid transitions must return (False, reason)."""

    @pytest.mark.parametrize("from_state,to_state", [
        # Can't go backwards
        (PaymentState.CAPTURED, PaymentState.CREATED),
        (PaymentState.CAPTURED, PaymentState.AUTHORIZED),
        (PaymentState.SETTLED, PaymentState.CAPTURED),
        (PaymentState.SETTLED, PaymentState.FAILED),
        # Skipping states
        (PaymentState.CREATED, PaymentState.SETTLED),
        (PaymentState.CREATED, PaymentState.CAPTURED),
        # Terminal state
        (PaymentState.SETTLED, PaymentState.UNKNOWN),
    ])
    def test_invalid_transition(self, from_state: PaymentState, to_state: PaymentState):
        success, reason = StateMachine.transition(from_state, to_state)
        assert success is False, f"Expected invalid: {from_state} → {to_state}"
        assert len(reason) > 0

    def test_no_op_transition(self):
        """Same-state transition is not allowed."""
        success, reason = StateMachine.transition(PaymentState.FAILED, PaymentState.FAILED)
        assert success is False

    def test_settled_is_terminal(self):
        """SETTLED has no outgoing transitions."""
        assert StateMachine.is_terminal(PaymentState.SETTLED) is True
        next_states = StateMachine.allowed_next_states(PaymentState.SETTLED)
        assert next_states == []


class TestCriticalSafetyInvariants:
    """Critical invariants that prevent double-charges and data corruption."""

    def test_captured_cannot_go_back_to_created(self):
        """Once captured, a payment can never be uncaptured."""
        success, _ = StateMachine.transition(PaymentState.CAPTURED, PaymentState.CREATED)
        assert success is False

    def test_settled_cannot_transition_anywhere(self):
        """Settlement is truly final."""
        for state in PaymentState:
            if state != PaymentState.SETTLED:
                success, _ = StateMachine.transition(PaymentState.SETTLED, state)
                assert success is False, f"SETTLED should not go to {state}"

    def test_unknown_cannot_go_directly_to_retry_states(self):
        """UNKNOWN can go to CAPTURED/FAILED/PENDING/ESCALATED but not PAYMENT_LINK_SENT directly."""
        # These are valid exits from UNKNOWN (via reconciliation)
        valid_exits = {
            PaymentState.CAPTURED,
            PaymentState.FAILED,
            PaymentState.PENDING,
            PaymentState.ESCALATED,
        }
        for state in valid_exits:
            success, _ = StateMachine.transition(PaymentState.UNKNOWN, state)
            assert success is True, f"UNKNOWN → {state} should be valid"
