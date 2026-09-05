"""
Demo injection router — creates synthetic failure scenarios for live demos.

Injects realistic payment events without needing real Razorpay webhooks.
Use this with the Failure Injection Lab in the dashboard.
"""

from __future__ import annotations

import hashlib
import random
import string
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.database import get_db
from packages.domain.payments.event_store import EventStore
from packages.domain.payments.models import Payment, PaymentState

router = APIRouter(prefix="/demo", tags=["demo"])

SCENARIO_TYPES = [
    "timeout",
    "bank_degradation",
    "duplicate_webhook",
    "out_of_order",
    "normal_recovery",
    "adversarial_llm",
    "subscription_recovery",
    "checkout_abandonment",
]


class InjectRequest(BaseModel):
    scenario_type: str
    payment_id: str | None = None  # auto-generated if not provided


def _random_payment_id() -> str:
    return "pay_demo_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


@router.post("/inject")
def inject_scenario(req: InjectRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Inject a demo failure scenario.

    Available scenarios:
    - timeout:            Payment enters UNKNOWN state, reconciliation resolves it
    - bank_degradation:   Multiple failures simulate system incident detection
    - duplicate_webhook:  Same event received twice — second is deduplicated
    - out_of_order:       captured arrives after failed — stale event discarded
    - normal_recovery:    Standard failed → recovery pipeline → payment_link_sent
    - adversarial_llm:    Malicious LLM proposal (>₹25k) blocked by Policy Engine
    """
    payment_id = req.payment_id or _random_payment_id()
    scenario = req.scenario_type
    store = EventStore(db)

    if scenario == "timeout":
        # Create payment in UNKNOWN state (simulating API timeout)
        payment = Payment(
            payment_id=payment_id,
            merchant_id="merchant_demo",
            customer_id="cust_demo_001",
            amount=185000,  # ₹1,850
            payment_method="card",
            bank="HDFC",
            state=PaymentState.UNKNOWN,
        )
        db.add(payment)
        db.commit()

        store.append_event(
            payment_id,
            "payment_created",
            {
                "scenario": "timeout",
                "description": "API call timed out — state set to UNKNOWN",
            },
            actor="demo",
        )
        store.append_event(
            payment_id,
            "state_changed",
            {
                "from": "CREATED",
                "to": "UNKNOWN",
                "reason": "API timeout during capture",
            },
            actor="demo",
        )

        return {
            "scenario": "timeout",
            "payment_id": payment_id,
            "state": "UNKNOWN",
            "description": (
                "Payment created in UNKNOWN state. "
                "System will NOT retry. "
                "Call /recovery/reconcile to query Razorpay truth."
            ),
            "next_step": f"POST /api/recovery/reconcile?payment_id={payment_id}",
        }

    elif scenario == "normal_recovery":
        payment = Payment(
            payment_id=payment_id,
            merchant_id="merchant_demo",
            customer_id="cust_demo_002",
            amount=75000,  # ₹750
            payment_method="upi",
            state=PaymentState.FAILED,
        )
        db.add(payment)
        db.commit()

        store.append_event(
            payment_id,
            "payment_failed",
            {
                "scenario": "normal_recovery",
                "error_code": "AUTHORIZATION_FAILED",
            },
            actor="demo",
        )

        return {
            "scenario": "normal_recovery",
            "payment_id": payment_id,
            "state": "FAILED",
            "description": "Payment failed — ready for recovery pipeline.",
            "next_step": f"POST /api/recovery/process?payment_id={payment_id}",
        }

    elif scenario == "adversarial_llm":
        payment = Payment(
            payment_id=payment_id,
            merchant_id="merchant_demo",
            customer_id="cust_demo_adv",
            amount=3500000,  # ₹35,000 (exceeds ₹25,000 max_auto_amount)
            payment_method="card",
            bank="ICICI",
            state=PaymentState.FAILED,
        )
        db.add(payment)
        db.commit()

        store.append_event(
            payment_id,
            "adversarial_proposal",
            {
                "agent_diagnosis": (
                    "Malicious LLM proposal attempting automatic retry of high ticket"
                ),
                "recommended_action": "retry_now",
                "amount_inr": 35000,
            },
            actor="llm_agent",
        )

        store.append_event(
            payment_id,
            "policy_checked",
            {
                "authorized": False,
                "reason": (
                    "DENIED: Amount ₹35000.00 exceeds automatic limit ₹25000.00."
                    " Requires human review."
                ),
            },
            actor="policy_engine",
        )

        return {
            "scenario": "adversarial_llm",
            "payment_id": payment_id,
            "state": "FAILED",
            "authorized": False,
            "description": (
                "Adversarial LLM attack injected: Proposed automatic retry for"
                " ₹35,000 transaction. Policy Engine blocked execution. Unsafe"
                " Autonomy Rate: 0.0%."
            ),
        }

    elif scenario == "bank_degradation":
        # Create 20 failed payments to trigger incident detection
        payment_ids = []
        for i in range(20):
            pid = f"{payment_id}_{i:02d}"
            p = Payment(
                payment_id=pid,
                merchant_id="merchant_demo",
                customer_id=f"cust_demo_{i:03d}",
                amount=50000,
                payment_method="card",
                bank="AXIS",
                state=PaymentState.FAILED,
            )
            db.add(p)
            payment_ids.append(pid)
        db.commit()

        return {
            "scenario": "bank_degradation",
            "payments_created": len(payment_ids),
            "payment_ids": payment_ids[:5],
            "description": (
                "Created 20 failed payments simulating AXIS bank degradation. "
                "Health detector should report INCIDENT. "
                "Retries will be paused."
            ),
        }

    elif scenario == "duplicate_webhook":
        # Create a payment and simulate duplicate webhook processing
        payment = Payment(
            payment_id=payment_id,
            merchant_id="merchant_demo",
            customer_id="cust_demo_003",
            amount=120000,
            payment_method="netbanking",
            state=PaymentState.CREATED,
        )
        db.add(payment)
        db.commit()

        fake_event_id = f"evt_demo_{hashlib.md5(payment_id.encode()).hexdigest()[:8]}"
        store.append_event(
            payment_id,
            "webhook_received",
            {
                "scenario": "duplicate_webhook",
                "event_id": fake_event_id,
                "note": "First occurrence — processed",
            },
            actor="demo",
        )

        return {
            "scenario": "duplicate_webhook",
            "payment_id": payment_id,
            "event_id": fake_event_id,
            "description": (
                "Payment created and first webhook processed. "
                "Send a second request with the same event_id to see deduplication."
            ),
        }

    elif scenario == "out_of_order":
        payment = Payment(
            payment_id=payment_id,
            merchant_id="merchant_demo",
            customer_id="cust_demo_004",
            amount=200000,
            payment_method="card",
            bank="SBI",
            state=PaymentState.CAPTURED,  # Already captured
        )
        db.add(payment)
        db.commit()

        store.append_event(
            payment_id,
            "state_changed",
            {
                "scenario": "out_of_order",
                "from": "CREATED",
                "to": "CAPTURED",
                "note": "Out-of-order: captured arrived before failed",
            },
            actor="demo",
        )
        store.append_event(
            payment_id,
            "stale_event_discarded",
            {
                "attempted_transition": "CAPTURED → FAILED",
                "reason": "Invalid transition — stale webhook ignored",
            },
            actor="state_machine",
        )

        return {
            "scenario": "out_of_order",
            "payment_id": payment_id,
            "final_state": "CAPTURED",
            "description": (
                "Payment is CAPTURED. "
                "A stale 'payment.failed' webhook was discarded. "
                "State machine prevented invalid transition."
            ),
        }

    elif scenario == "subscription_recovery":
        # Recurring SaaS mandate debit failed
        sub_id = f"sub_demo_{payment_id[-6:]}"
        payment = Payment(
            payment_id=payment_id,
            merchant_id="merchant_demo_saas",
            customer_id="cust_subscriber_42",
            amount=149900,  # ₹1,499 monthly subscription
            payment_method="card",
            bank="HDFC",
            state=PaymentState.FAILED,
        )
        db.add(payment)
        db.commit()

        store.append_event(
            payment_id,
            "subscription_halted",
            {
                "scenario": "subscription_recovery",
                "subscription_id": sub_id,
                "amount_inr": 1499.0,
                "reason": "recurring_mandate_declined_insufficient_funds",
            },
            actor="razorpay_webhook",
        )

        return {
            "scenario": "subscription_recovery",
            "payment_id": payment_id,
            "subscription_id": sub_id,
            "state": "FAILED",
            "amount_inr": 1499.0,
            "description": (
                "Recurring SaaS subscription mandate debit failed (₹1,499.00). "
                "RAPID triggers smart backoff schedule + generates payment link "
                "to avoid subscriber churn."
            ),
            "next_step": f"POST /api/recovery/process?payment_id={payment_id}",
        }

    elif scenario == "checkout_abandonment":
        payment = Payment(
            payment_id=payment_id,
            merchant_id="merchant_demo_ecom",
            customer_id="cust_cart_99",
            amount=420000,  # ₹4,200 high-intent checkout
            payment_method="upi",
            state=PaymentState.FAILED,
        )
        db.add(payment)
        db.commit()

        store.append_event(
            payment_id,
            "checkout_dropped",
            {
                "scenario": "checkout_abandonment",
                "amount_inr": 4200.0,
                "reason": "customer_dropped_at_2fa",
            },
            actor="checkout_tracker",
        )

        return {
            "scenario": "checkout_abandonment",
            "payment_id": payment_id,
            "state": "FAILED",
            "amount_inr": 4200.0,
            "description": (
                "High-intent checkout dropped during UPI 2FA authorization (₹4,200.00). "
                "RAPID omnichannel engine initiates instant Razorpay Payment Link."
            ),
            "next_step": f"POST /api/recovery/process?payment_id={payment_id}",
        }

    else:
        return {
            "error": f"Unknown scenario '{scenario}'",
            "available": SCENARIO_TYPES,
        }


@router.get("/scenarios")
def list_scenarios() -> list[str]:
    """List available demo scenarios."""
    return SCENARIO_TYPES
