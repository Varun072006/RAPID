"""Payments API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.database import get_db
from packages.domain.payments.models import Payment, PaymentState
from packages.utils.audit import AuditLogger

router = APIRouter(tags=["payments"])


class CreatePaymentRequest(BaseModel):
    payment_id: str
    merchant_id: str
    customer_id: str
    amount: int  # in paise
    payment_method: str = "card"
    bank: str | None = None
    razorpay_payment_id: str | None = None


@router.post("/payments", status_code=201)
def create_payment(req: CreatePaymentRequest, db: Session = Depends(get_db)) -> dict:
    """Create a new payment record."""
    existing = db.query(Payment).filter(Payment.payment_id == req.payment_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Payment already exists")

    payment = Payment(
        payment_id=req.payment_id,
        merchant_id=req.merchant_id,
        customer_id=req.customer_id,
        amount=req.amount,
        payment_method=req.payment_method,
        bank=req.bank,
        razorpay_payment_id=req.razorpay_payment_id,
        state=PaymentState.CREATED,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return {"payment_id": payment.payment_id, "state": payment.state.value}


@router.get("/payments")
def list_payments(
    limit: int = 20,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """List recent payments, optionally filtered by state."""
    query = db.query(Payment).order_by(Payment.created_at.desc())
    if state:
        try:
            query = query.filter(Payment.state == PaymentState(state))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid state: {state}")
    payments = query.limit(limit).all()
    return [
        {
            "payment_id": p.payment_id,
            "amount": p.amount,
            "state": p.state.value,
            "payment_method": p.payment_method,
            "bank": p.bank,
            "retry_count": p.retry_count,
            "created_at": p.created_at.isoformat(),
        }
        for p in payments
    ]


@router.get("/payments/{payment_id}")
def get_payment(payment_id: str, db: Session = Depends(get_db)) -> dict:
    """Get a single payment by ID."""
    payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {
        "payment_id": payment.payment_id,
        "merchant_id": payment.merchant_id,
        "customer_id": payment.customer_id,
        "amount": payment.amount,
        "state": payment.state.value,
        "failure_mode": payment.failure_mode,
        "retry_count": payment.retry_count,
        "payment_method": payment.payment_method,
        "bank": payment.bank,
        "created_at": payment.created_at.isoformat(),
        "updated_at": payment.updated_at.isoformat(),
    }


@router.get("/payments/{payment_id}/timeline")
def get_timeline(payment_id: str, db: Session = Depends(get_db)) -> list[dict]:
    """Get full audit timeline for a payment (replay-ready)."""
    audit = AuditLogger(db)
    timeline = audit.get_timeline(payment_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="No events found for this payment")
    return timeline


@router.post("/recovery/process")
def process_recovery(payment_id: str, db: Session = Depends(get_db)) -> dict:
    """
    Trigger recovery pipeline for a failed payment.
    Requires ML models to be trained (make data && make train).
    """
    from apps.api.config import get_settings
    from packages.domain.policy.engine import PolicyEngine
    from packages.domain.recovery.optimizer import RevenueOptimizer
    from packages.domain.recovery.system_health import HealthDetector
    from packages.workflows.recovery.agent import RecoveryAgent
    from packages.workflows.recovery.orchestrator import RecoveryOrchestrator

    settings = get_settings()

    if settings.use_mock_razorpay:
        from packages.integrations.razorpay.mock_adapter import MockRazorpayAdapter
        razorpay = MockRazorpayAdapter()
    else:
        from packages.integrations.razorpay.adapter import RazorpayAdapter
        razorpay = RazorpayAdapter(
            settings.razorpay_key_id,
            settings.razorpay_key_secret,
            settings.razorpay_webhook_secret,
        )

    orchestrator = RecoveryOrchestrator(
        razorpay=razorpay,
        optimizer=RevenueOptimizer(),
        policy=PolicyEngine(),
        health_detector=HealthDetector(),
        agent=RecoveryAgent(
            model=settings.llm_model,
            ollama_host=settings.ollama_host,
            provider=settings.llm_provider,
        ),
        db=db,
    )

    try:
        return orchestrator.process_failed_payment(payment_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
