"""Payments API router."""

from __future__ import annotations

from typing import Any

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
def create_payment(req: CreatePaymentRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
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
) -> list[dict[str, Any]]:
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
def get_payment(payment_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
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
def get_timeline(payment_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Get full audit timeline for a payment (replay-ready)."""
    audit = AuditLogger(db)
    timeline = audit.get_timeline(payment_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="No events found for this payment")
    return timeline


@router.post("/recovery/process")
def process_recovery(payment_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
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
    razorpay: Any

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


class ReconcileRequest(BaseModel):
    payment_id: str
    razorpay_payment_id: str | None = None


@router.post("/recovery/reconcile")
def reconcile_payment(
    payment_id: str | None = None,
    req: ReconcileRequest | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Reconcile an UNKNOWN or timed-out payment with Razorpay's authoritative state.
    Enforces idempotency and guarantees zero double-charge risk before any retry.
    """
    from apps.api.config import get_settings
    from packages.domain.payments.event_store import EventStore
    from packages.workflows.reconciliation.unknown_state import UnknownStateResolver

    pid = (req.payment_id if req else None) or payment_id
    if not pid:
        raise HTTPException(
            status_code=400,
            detail="payment_id query param or request body is required",
        )

    payment = db.query(Payment).filter(Payment.payment_id == pid).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {pid} not found")

    rzp_id = str(
        (req.razorpay_payment_id if req else None)
        or payment.razorpay_payment_id
        or f"pay_{pid}"
    )

    settings = get_settings()
    razorpay: Any
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

    resolver = UnknownStateResolver(razorpay=razorpay, db=db)
    result = resolver.apply_reconciliation(payment_id=pid, razorpay_payment_id=rzp_id)

    store = EventStore(db)
    store.append_event(
        pid,
        "reconciliation_completed",
        result,
        actor="reconciler",
    )

    prev_state_str = payment.state.value if hasattr(payment.state, "value") else str(payment.state)
    next_state_val = result["next_state"]
    next_state_str = (
        next_state_val.value if hasattr(next_state_val, "value") else str(next_state_val)
    )

    return {
        "payment_id": pid,
        "previous_state": prev_state_str,
        "reconciled_state": next_state_str,
        "outcome": result["outcome"],
        "message": result["message"],
        "safe_to_retry": result["safe_to_retry"],
        "razorpay_id": rzp_id,
    }


class BatchRecoverRequest(BaseModel):
    payment_ids: list[str] | None = None
    limit: int = 25


@router.post("/batch/recover")
def batch_recover(
    req: BatchRecoverRequest | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Recover a batch of failed payments autonomously.
    Measures cumulative money recovered, action distributions, and policy safety checks.
    """
    from apps.api.config import get_settings
    from packages.domain.policy.engine import PolicyEngine
    from packages.domain.recovery.optimizer import RevenueOptimizer
    from packages.domain.recovery.system_health import HealthDetector
    from packages.workflows.recovery.agent import RecoveryAgent
    from packages.workflows.recovery.orchestrator import RecoveryOrchestrator

    settings = get_settings()
    razorpay: Any
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

    # Determine payments to process
    batch_pids: list[str] = []
    if req and req.payment_ids:
        batch_pids = req.payment_ids
    else:
        limit = req.limit if req else 25
        failed_payments = (
            db.query(Payment)
            .filter(Payment.state == PaymentState.FAILED)
            .limit(limit)
            .all()
        )
        batch_pids = [str(p.payment_id) for p in failed_payments]

    if not batch_pids:
        return {
            "total_processed": 0,
            "recovered_count": 0,
            "gross_amount_attempted_inr": 0.0,
            "net_revenue_recovered_inr": 0.0,
            "action_breakdown": {},
            "results": [],
            "message": "No failed payments eligible for batch recovery",
        }

    results = []
    action_breakdown = {"retry_now": 0, "retry_later": 0, "payment_link": 0, "do_nothing": 0}
    gross_attempted_paise = 0
    net_recovered_paise = 0
    recovered_count = 0

    for pid in batch_pids:
        p = db.query(Payment).filter(Payment.payment_id == pid).first()
        if p:
            gross_attempted_paise += int(p.amount)
        try:
            res = orchestrator.process_failed_payment(pid)
            results.append(res)
            act = res.get("action", "do_nothing")
            action_breakdown[act] = action_breakdown.get(act, 0) + 1
            if res.get("authorized", False) and res.get("success", False):
                recovered_count += 1
                ev = res.get("expected_value_inr", 0.0)
                net_recovered_paise += int(ev * 100)
        except Exception as exc:
            results.append({"payment_id": pid, "error": str(exc)})

    return {
        "total_processed": len(batch_pids),
        "recovered_count": recovered_count,
        "recovery_rate": round(recovered_count / len(batch_pids), 4) if batch_pids else 0.0,
        "gross_amount_attempted_inr": round(gross_attempted_paise / 100.0, 2),
        "net_revenue_recovered_inr": round(net_recovered_paise / 100.0, 2),
        "action_breakdown": action_breakdown,
        "results": results,
    }

