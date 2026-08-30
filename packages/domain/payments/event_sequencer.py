"""
Event sequencer — handles out-of-order webhook events.

Razorpay webhooks are not guaranteed to arrive in chronological order.
Example scenario:
    1. payment.captured  arrives at t=10s
    2. payment.failed    arrives at t=15s  ← stale, already captured

The sequencer validates each incoming event against the current state
via the state machine. Invalid (stale) transitions are silently dropped
with a warning log — they do NOT raise exceptions or change state.
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session

from packages.domain.payments.models import Payment, PaymentState
from packages.domain.payments.state_machine import StateMachine


class EventSequencer:
    """
    Validates and applies incoming state transition events.

    Workflow:
        1. Load current payment state from DB.
        2. Validate transition via StateMachine.
        3. If valid → update state + commit.
        4. If invalid → log warning + return (False, reason).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def process_event(
        self,
        payment_id: str,
        event_type: str,
        new_state: PaymentState,
        details: dict | None = None,
    ) -> tuple[bool, str]:
        """
        Process an incoming event for a payment.

        Args:
            payment_id:  Internal payment ID.
            event_type:  Human-readable event type (for logging).
            new_state:   Desired new state.
            details:     Optional extra context.

        Returns:
            (True, "OK")            — transition applied.
            (False, reason: str)    — stale/invalid event, caller should discard.
        """
        payment = (
            self.db.query(Payment)
            .filter(Payment.payment_id == payment_id)
            .first()
        )

        if not payment:
            logger.warning(
                f"EventSequencer: payment {payment_id} not found "
                f"for event {event_type}"
            )
            return False, f"Payment {payment_id} not found"

        current_state = PaymentState(payment.state)
        is_valid, reason = StateMachine.transition(current_state, new_state)

        if not is_valid:
            logger.warning(
                f"Stale/invalid event for {payment_id}: "
                f"event={event_type} "
                f"current={current_state.value} → "
                f"requested={new_state.value} | {reason}"
            )
            return False, f"Stale event: {reason}"

        # Apply valid transition
        previous_state = payment.state
        payment.state = new_state
        self.db.commit()

        logger.info(
            f"State transition applied: payment={payment_id} "
            f"{previous_state} → {new_state.value} (event={event_type})"
        )
        return True, "OK"
