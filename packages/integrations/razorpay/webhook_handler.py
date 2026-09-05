"""
Razorpay webhook handler — FastAPI router.

Workflow for each incoming webhook:
1. Read raw body (signature verification requires raw bytes)
2. Extract and verify HMAC-SHA256 signature
3. Extract Razorpay event ID (deduplication key)
4. Deduplication check (DB-backed, atomic)
5. Parse JSON payload
6. Map Razorpay event → internal state transition
7. Apply via EventSequencer (handles out-of-order)
8. Append to audit log
9. Return 200 ACK

Note: We always return 200 to Razorpay even for duplicates.
Returning 4xx/5xx causes Razorpay to retry, flooding us with duplicates.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy.orm import Session

from packages.domain.payments.deduplicator import Deduplicator
from packages.domain.payments.event_sequencer import EventSequencer
from packages.domain.payments.event_store import EventStore
from packages.domain.payments.models import Payment, PaymentState
from packages.integrations.razorpay.adapter import RazorpayAdapter

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Razorpay event type → internal PaymentState mapping
RAZORPAY_EVENT_TO_STATE: dict[str, PaymentState] = {
    "payment.authorized": PaymentState.AUTHORIZED,
    "payment.captured": PaymentState.CAPTURED,
    "payment.failed": PaymentState.FAILED,
    "payment_link.paid": PaymentState.CAPTURED,
}


def get_payment_id_from_payload(payload: dict[str, Any]) -> str | None:
    """Extract the payment ID from a Razorpay webhook payload."""
    try:
        entity = payload.get("payload", {})
        # Different event types nest differently
        payment = entity.get("payment", {}).get("entity", {})
        if payment_id := payment.get("id"):
            return str(payment_id)
        link = entity.get("payment_link", {}).get("entity", {})
        link_id = link.get("id")
        return str(link_id) if link_id else None
    except (KeyError, AttributeError):
        return None


@router.post("/razorpay")
async def receive_razorpay_webhook(
    request: Request,
    db: Session = Depends(lambda: None),  # replaced by real dep in main.py
    razorpay: RazorpayAdapter = Depends(lambda: None),
) -> dict[str, Any]:
    """
    Receive and process a payment event webhook from Razorpay.

    Always returns 200 — never 4xx/5xx to Razorpay (would cause retries).
    """
    # Step 1: Read raw body
    raw_body = await request.body()

    # Step 2: Verify HMAC-SHA256 signature
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not signature:
        logger.warning("Webhook received without X-Razorpay-Signature header")
        raise HTTPException(status_code=403, detail="Missing signature")

    if not razorpay.verify_webhook_signature(raw_body, signature):
        logger.warning("Invalid webhook signature — possible spoofing attempt")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Step 3: Parse JSON
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("Webhook body is not valid JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = payload.get("event", "unknown")

    # Step 4: Extract event ID
    event_id = request.headers.get("X-Razorpay-Event-Id", "")
    if not event_id:
        # Fallback: use hash of raw body as event ID
        import hashlib

        event_id = hashlib.sha256(raw_body).hexdigest()[:32]
        logger.warning(f"Missing X-Razorpay-Event-Id, using body hash: {event_id}")

    # Step 5: Deduplication
    dedup = Deduplicator(db)
    if dedup.is_duplicate(event_id):
        logger.info(f"Duplicate webhook suppressed: {event_id} ({event_type})")
        return {"status": "deduplicated", "event_id": event_id}

    # Step 6: Extract payment ID
    razorpay_payment_id = get_payment_id_from_payload(payload)

    # Step 7: Mark processed (atomic — race condition safe)
    dedup.mark_processed(event_id, event_type, payload)

    # Step 8: Map to internal state + apply transition
    new_state = RAZORPAY_EVENT_TO_STATE.get(event_type)
    if new_state and razorpay_payment_id:
        payment = (
            db.query(Payment).filter(Payment.razorpay_payment_id == razorpay_payment_id).first()
        )
        if payment:
            sequencer = EventSequencer(db)
            applied, reason = sequencer.process_event(
                str(payment.payment_id),
                event_type,
                new_state,
                details={"razorpay_event_id": event_id},
            )
            logger.info(
                f"Webhook {event_id}: "
                f"payment={payment.payment_id} "
                f"applied={applied} reason={reason}"
            )

    # Step 9: Append to audit log
    store = EventStore(db)
    store.append_event(
        payment_id=razorpay_payment_id or "unknown",
        event_type="webhook_received",
        data={
            "razorpay_event_id": event_id,
            "event_type": event_type,
            "received_at": datetime.utcnow().isoformat(),
        },
        actor="razorpay_webhook",
    )

    logger.info(f"Webhook processed: {event_id} ({event_type})")
    return {"status": "acknowledged", "event_id": event_id}
