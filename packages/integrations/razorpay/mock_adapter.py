"""
Mock Razorpay adapter — runs without real Razorpay credentials.

When RAZORPAY_MODE=mock, this adapter is used instead of the real one.
All API calls are intercepted and return realistic simulated responses.

This lets you:
- Develop and test locally without a Razorpay account
- Run CI without secrets
- Demo the system without live API calls

To get real Test Mode keys (free, instant):
1. Go to https://razorpay.com
2. Sign up (no payment required)
3. Go to Settings → API Keys → Generate Test Key
4. Copy key_id and key_secret into .env
5. Set RAZORPAY_MODE=test
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from loguru import logger


class MockRazorpayAdapter:
    """
    Simulated Razorpay adapter for local development without real credentials.

    Behaviour:
    - fetch_payment: returns a simulated status (captured/failed/authorized)
      based on the payment ID hash (deterministic but varied)
    - create_payment_link: returns a fake payment link URL
    - verify_webhook_signature: always returns True in mock mode
      (set RAZORPAY_MOCK_REJECT_SIGS=true to simulate rejection)
    """

    def __init__(
        self,
        key_id: str = "rzp_test_mock",
        key_secret: str = "mock_secret",
        webhook_secret: str = "mock_webhook_secret",
    ) -> None:
        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret
        self.mode = "mock"
        logger.warning(
            "MockRazorpayAdapter active — no real Razorpay API calls will be made. "
            "Set RAZORPAY_MODE=test to use real Test Mode keys."
        )

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        """In mock mode, verify using the mock secret (or accept all)."""
        try:
            expected = hmac.new(
                self.webhook_secret.encode(),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return True  # Accept all in mock mode

    def fetch_payment(self, razorpay_payment_id: str) -> dict[str, Any]:
        """
        Simulate Razorpay payment fetch.

        Uses a hash of the payment ID to deterministically vary the result,
        so the same payment always returns the same simulated state.
        """
        # Deterministic pseudo-random based on payment ID
        seed = int(hashlib.md5(razorpay_payment_id.encode()).hexdigest(), 16) % 100

        if seed < 60:
            status = "captured"
        elif seed < 80:
            status = "failed"
        elif seed < 90:
            status = "authorized"
        else:
            status = "created"

        logger.debug(f"[MOCK] fetch_payment({razorpay_payment_id}) → status={status}")

        return {
            "id": razorpay_payment_id,
            "entity": "payment",
            "amount": 100000,  # ₹1,000 in paise
            "currency": "INR",
            "status": status,
            "created_at": int(time.time()),
            "description": "Mock payment",
            "error_code": "BAD_REQUEST_ERROR" if status == "failed" else None,
            "error_description": (
                "Payment failed due to issuer timeout" if status == "failed" else None
            ),
        }

    def create_payment_link(
        self,
        amount: int,
        customer_id: str,
        description: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Simulate payment link creation."""
        link_id = f"plink_mock_{idempotency_key[:8]}"
        short_url = f"https://rzp.io/mock/{link_id}"

        logger.info(
            f"[MOCK] create_payment_link: amount={amount} "
            f"customer={customer_id} link={short_url}"
        )

        return {
            "id": link_id,
            "entity": "payment_link",
            "amount": amount,
            "currency": "INR",
            "status": "created",
            "short_url": short_url,
            "customer_id": customer_id,
            "description": description,
            "created_at": int(time.time()),
        }

    def fetch_order(self, order_id: str) -> dict[str, Any]:
        """Simulate order fetch."""
        return {
            "id": order_id,
            "entity": "order",
            "amount": 100000,
            "currency": "INR",
            "status": "created",
        }
