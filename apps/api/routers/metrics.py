"""Metrics API router — JSON summary for the dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.database import get_db
from packages.domain.payments.models import Payment, PaymentState, RecoveryDecision

router = APIRouter(tags=["metrics"])


@router.get("/metrics/summary")
def get_metrics_summary(db: Session = Depends(get_db)) -> dict:
    """
    Return business metrics summary for the dashboard.
    Computed fresh from DB on each request (suitable for prototype).
    """
    total_payments = db.query(Payment).count()
    failed_payments = db.query(Payment).filter(Payment.state == PaymentState.FAILED).count()
    unknown_payments = db.query(Payment).filter(Payment.state == PaymentState.UNKNOWN).count()
    captured_payments = db.query(Payment).filter(Payment.state == PaymentState.CAPTURED).count()
    link_sent_payments = (
        db.query(Payment).filter(Payment.state == PaymentState.PAYMENT_LINK_SENT).count()
    )

    # Revenue at risk: sum of failed + unknown payment amounts
    at_risk_payments = (
        db.query(Payment)
        .filter(Payment.state.in_([PaymentState.FAILED, PaymentState.UNKNOWN]))
        .all()
    )
    revenue_at_risk = sum(p.amount for p in at_risk_payments)

    total_decisions = db.query(RecoveryDecision).count()
    policy_denied = (
        db.query(RecoveryDecision).filter(RecoveryDecision.policy_authorized.is_(False)).count()
    )

    # Recovery rate approximation
    recovery_rate = (
        (captured_payments + link_sent_payments) / max(1, failed_payments) * 100
        if failed_payments > 0
        else 0.0
    )

    return {
        "total_payments": total_payments,
        "failed_payments": failed_payments,
        "unknown_payments": unknown_payments,
        "captured_payments": captured_payments,
        "link_sent_payments": link_sent_payments,
        "revenue_at_risk_paise": revenue_at_risk,
        "revenue_at_risk_inr": revenue_at_risk / 100,
        "recovery_rate": round(recovery_rate, 2),
        "total_decisions": total_decisions,
        "policy_denied": policy_denied,
        "system_healthy": unknown_payments < 10,  # simple heuristic
    }
