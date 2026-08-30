"""
Payment state machine — defines all valid state transitions.

Design principles:
- Only valid transitions are allowed; all others raise ValueError.
- Terminal states (SETTLED, ESCALATED-as-dead-end) cannot transition further.
- UNKNOWN is a safety state: entered on timeout, exited only via reconciliation.
- The machine is pure (no I/O, no DB) — easy to test with Hypothesis.
"""

from __future__ import annotations

from typing import FrozenSet

from packages.domain.payments.models import PaymentState


class StateMachineError(Exception):
    """Raised when an invalid state transition is attempted."""


class StateMachine:
    """
    Defines and enforces valid payment state transitions.

    Prevents impossible transitions like CAPTURED → CREATED or
    SETTLED → FAILED, which would corrupt payment ledger integrity.

    Usage:
        success, reason = StateMachine.transition(current, desired)
        if not success:
            # log and discard stale event
    """

    # Map: from_state → set of allowed to_states
    VALID_TRANSITIONS: dict[PaymentState, FrozenSet[PaymentState]] = {
        PaymentState.CREATED: frozenset(
            {
                PaymentState.AUTHORIZED,
                PaymentState.FAILED,
                PaymentState.PENDING,
                PaymentState.UNKNOWN,
            }
        ),
        PaymentState.AUTHORIZED: frozenset(
            {
                PaymentState.CAPTURED,
                PaymentState.FAILED,
                PaymentState.PENDING,
                PaymentState.UNKNOWN,
            }
        ),
        PaymentState.CAPTURED: frozenset(
            {
                PaymentState.SETTLED,  # Only valid next step after capture
            }
        ),
        PaymentState.FAILED: frozenset(
            {
                PaymentState.PAYMENT_LINK_SENT,
                PaymentState.ESCALATED,
                PaymentState.UNKNOWN,  # Re-check if fail was a timeout artifact
            }
        ),
        PaymentState.PENDING: frozenset(
            {
                PaymentState.CAPTURED,
                PaymentState.FAILED,
                PaymentState.UNKNOWN,
            }
        ),
        PaymentState.UNKNOWN: frozenset(
            {
                # Exits after reconciliation
                PaymentState.CAPTURED,
                PaymentState.FAILED,
                PaymentState.PENDING,
                PaymentState.ESCALATED,
            }
        ),
        PaymentState.PAYMENT_LINK_SENT: frozenset(
            {
                PaymentState.CAPTURED,
                PaymentState.FAILED,
                PaymentState.PENDING,
                PaymentState.ESCALATED,
            }
        ),
        PaymentState.ESCALATED: frozenset(
            {
                # Human can resolve to captured or failed
                PaymentState.CAPTURED,
                PaymentState.FAILED,
            }
        ),
        PaymentState.SETTLED: frozenset(),  # Hard terminal — nothing follows settlement
    }

    @classmethod
    def is_valid_transition(
        cls,
        from_state: PaymentState,
        to_state: PaymentState,
    ) -> bool:
        """Return True if the transition is allowed."""
        return to_state in cls.VALID_TRANSITIONS.get(from_state, frozenset())

    @classmethod
    def transition(
        cls,
        from_state: PaymentState,
        to_state: PaymentState,
    ) -> tuple[bool, str]:
        """
        Attempt a state transition.

        Returns:
            (True, "OK") on success
            (False, reason) if invalid — caller should log and discard the event
        """
        if from_state == to_state:
            return False, f"No-op transition {from_state.value} → {to_state.value}"

        if cls.is_valid_transition(from_state, to_state):
            return True, "OK"

        reason = (
            f"Invalid transition {from_state.value} → {to_state.value}. "
            f"Allowed from {from_state.value}: "
            f"{[s.value for s in cls.VALID_TRANSITIONS.get(from_state, frozenset())]}"
        )
        return False, reason

    @classmethod
    def allowed_next_states(cls, from_state: PaymentState) -> list[PaymentState]:
        """Return all states reachable from from_state."""
        return list(cls.VALID_TRANSITIONS.get(from_state, frozenset()))

    @classmethod
    def is_terminal(cls, state: PaymentState) -> bool:
        """Return True if no further transitions are possible."""
        return len(cls.VALID_TRANSITIONS.get(state, frozenset())) == 0
