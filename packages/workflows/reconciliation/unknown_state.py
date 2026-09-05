"""
Unknown-state reconciler — the most critical safety component in RAPID.

Problem:
    Network timeouts are common. When an API call times out, we don't
    know whether the operation succeeded or failed on the server side.
    Retrying blindly risks double-charging customers.

Solution:
    Mark the payment as UNKNOWN (a safety state) and query Razorpay's
    authoritative state before deciding on any further action.

Invariant:
    RAPID never retries a payment in UNKNOWN state without
    first reconciling with Razorpay.
"""

from __future__ import annotations

import enum
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from packages.domain.payments.models import Payment, PaymentState


class ReconciliationOutcome(str, enum.Enum):
    """Result of querying Razorpay for authoritative state."""

    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"  # Razorpay itself couldn't tell us


class UnknownStateResolver:
    """
    Resolves UNKNOWN payment state by querying Razorpay's truth.

    This is the safety boundary that prevents double-charges.
    The system enters this resolver whenever:
    - An API call times out
    - A webhook is ambiguous
    - Manual reconciliation is requested
    """

    def __init__(self, razorpay: Any, db: Session) -> None:
        self.razorpay = razorpay
        self.db = db

    def reconcile(self, razorpay_payment_id: str) -> ReconciliationOutcome:
        """
        Query Razorpay for the authoritative payment state.

        Maps Razorpay's status strings to our ReconciliationOutcome enum.
        If Razorpay itself is unavailable, returns UNKNOWN (safe default).
        """
        try:
            payment = self.razorpay.fetch_payment(razorpay_payment_id)
        except Exception as exc:
            logger.error(
                f"Reconciliation query failed for {razorpay_payment_id}: {exc}. "
                f"Defaulting to UNKNOWN (safe)."
            )
            return ReconciliationOutcome.UNKNOWN

        status = payment.get("status", "")

        if status == "captured":
            return ReconciliationOutcome.CAPTURED
        elif status == "failed":
            return ReconciliationOutcome.FAILED
        elif status in ("authorized", "created"):
            return ReconciliationOutcome.PENDING
        else:
            logger.warning(
                f"Unrecognized Razorpay status '{status}' "
                f"for {razorpay_payment_id} — treating as UNKNOWN"
            )
            return ReconciliationOutcome.UNKNOWN

    def handle_timeout(
        self,
        payment_id: str,
        razorpay_payment_id: str,
    ) -> dict[str, Any]:
        """
        Handle the timeout scenario.

        Returns a structured dict describing:
        - outcome: what we found
        - message: human-readable explanation
        - safe_to_retry: whether it is safe to re-attempt
        - next_state: recommended internal state update
        """
        logger.info(
            f"Timeout reconciliation started: "
            f"payment={payment_id} razorpay_id={razorpay_payment_id}"
        )

        true_state = self.reconcile(razorpay_payment_id)

        if true_state == ReconciliationOutcome.CAPTURED:
            logger.info(
                f"Reconciliation: {payment_id} was actually CAPTURED. "
                f"Timeout was on the response, not the transaction."
            )
            return {
                "outcome": "SUCCESS_ON_RECONCILIATION",
                "message": (
                    "Payment was captured successfully. "
                    "The timeout occurred on the response path, not the transaction. "
                    "No further action needed."
                ),
                "safe_to_retry": False,
                "next_state": PaymentState.CAPTURED,
                "razorpay_id": razorpay_payment_id,
            }

        elif true_state == ReconciliationOutcome.FAILED:
            logger.info(f"Reconciliation: {payment_id} confirmed FAILED. Safe to recover.")
            return {
                "outcome": "CONFIRMED_FAILED",
                "message": (
                    "Payment definitively failed. "
                    "It is safe to retry or choose an alternative recovery action."
                ),
                "safe_to_retry": True,
                "next_state": PaymentState.FAILED,
                "razorpay_id": razorpay_payment_id,
            }

        elif true_state == ReconciliationOutcome.PENDING:
            logger.info(
                f"Reconciliation: {payment_id} still PENDING. "
                f"NOT safe to retry — risk of duplicate charge."
            )
            return {
                "outcome": "STILL_PENDING",
                "message": (
                    "Payment is still being processed by the bank. "
                    "Do NOT retry — this risks a duplicate charge. "
                    "Wait for the next webhook event."
                ),
                "safe_to_retry": False,
                "next_state": PaymentState.PENDING,
                "razorpay_id": razorpay_payment_id,
            }

        else:  # UNKNOWN
            logger.warning(
                f"Reconciliation: {payment_id} state still UNKNOWN after query. "
                f"Escalating to human review."
            )
            return {
                "outcome": "STILL_UNKNOWN",
                "message": (
                    "Could not determine authoritative payment state from Razorpay. "
                    "Escalating to human review. Do NOT retry automatically."
                ),
                "safe_to_retry": False,
                "next_state": PaymentState.ESCALATED,
                "razorpay_id": razorpay_payment_id,
            }

    def apply_reconciliation(
        self,
        payment_id: str,
        razorpay_payment_id: str,
    ) -> dict[str, Any]:
        """Reconcile and apply the state update to the database."""
        result = self.handle_timeout(payment_id, razorpay_payment_id)

        payment = self.db.query(Payment).filter(Payment.payment_id == payment_id).first()
        if payment:
            payment.state = result["next_state"]
            self.db.commit()
            logger.info(f"Reconciliation applied: {payment_id} → {result['next_state'].value}")

        return result
