"""
Razorpay adapter — all Razorpay API interactions live here.

This is the only file that knows about Razorpay. The rest of the
codebase uses domain types and never touches Razorpay APIs directly.

Design decisions:
- Webhook signature verification is done over the RAW request body
  (not parsed JSON), as Razorpay specifies.
- All mutating calls include an Idempotency-Key header.
- Retries are NOT implemented here — the orchestrator handles retry logic.
- Timeouts are short (5s) — callers handle timeout exceptions.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, cast

import requests
from loguru import logger


class RazorpayError(Exception):
    """Raised when a Razorpay API call fails."""


class RazorpayAdapter:
    """
    Razorpay Test Mode integration.

    All Razorpay-specific logic is isolated here. Swap this class for
    a mock in tests, or for a different PSP in production.
    """

    BASE_URL = "https://api.razorpay.com/v1"
    DEFAULT_TIMEOUT = 5  # seconds

    def __init__(
        self,
        key_id: str,
        key_secret: str,
        webhook_secret: str,
        mode: str = "test",
    ) -> None:
        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret
        self.mode = mode
        self._auth = (key_id, key_secret)

    # ─── Webhook verification ──────────────────────────────────

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature: str,
    ) -> bool:
        """
        Verify Razorpay webhook signature.

        CRITICAL: verification must be over the RAW request body bytes,
        NOT over the parsed JSON. Razorpay signs the raw body.
        """
        try:
            expected = hmac.new(
                self.webhook_secret.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as exc:
            logger.error(f"Signature verification error: {exc}")
            return False

    # ─── Payment queries ───────────────────────────────────────

    def fetch_payment(self, razorpay_payment_id: str) -> dict[str, Any]:
        """
        Query the authoritative payment state from Razorpay.

        Used for reconciliation when local state is UNKNOWN.
        May raise requests.Timeout or RazorpayError — callers must handle.
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/payments/{razorpay_payment_id}",
                auth=self._auth,
                timeout=self.DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            data = cast(dict[str, Any], response.json())
            logger.debug(f"Fetched payment {razorpay_payment_id}: status={data.get('status')}")
            return data
        except requests.Timeout:
            logger.error(f"Timeout fetching payment {razorpay_payment_id} from Razorpay")
            raise
        except requests.HTTPError as exc:
            logger.error(f"Razorpay API error for {razorpay_payment_id}: {exc}")
            raise RazorpayError(str(exc)) from exc

    # ─── Recovery actions ──────────────────────────────────────

    def create_payment_link(
        self,
        amount: int,
        customer_id: str,
        description: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """
        Create a payment link as a recovery action.

        Test Mode fully supports Payment Links — this is a legitimate
        recovery flow (not a workaround).

        Args:
            amount:          Amount in paise.
            customer_id:     Razorpay customer ID.
            description:     Payment description shown to customer.
            idempotency_key: Stable key — safe to retry this call.

        Returns:
            Razorpay payment link object.
        """
        headers = {
            "Idempotency-Key": idempotency_key,
            "Content-Type": "application/json",
        }
        payload = {
            "amount": amount,
            "currency": "INR",
            "customer_id": customer_id,
            "description": description,
            "notify": {"sms": True, "email": True},
        }
        try:
            response = requests.post(
                f"{self.BASE_URL}/payment_links",
                auth=self._auth,
                json=payload,
                headers=headers,
                timeout=self.DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            data = cast(dict[str, Any], response.json())
            logger.info(
                f"Payment link created: {data.get('id')} for customer {customer_id} "
                f"amount={amount} idempotency_key={idempotency_key}"
            )
            return data
        except requests.Timeout:
            logger.error("Timeout creating payment link")
            raise
        except requests.HTTPError as exc:
            logger.error(f"Failed to create payment link: {exc}")
            raise RazorpayError(str(exc)) from exc

    def fetch_order(self, order_id: str) -> dict[str, Any]:
        """Fetch a Razorpay order (for retry flows)."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/orders/{order_id}",
                auth=self._auth,
                timeout=self.DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except requests.HTTPError as exc:
            raise RazorpayError(str(exc)) from exc

    def fetch_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Fetch Razorpay subscription details."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/subscriptions/{subscription_id}",
                auth=self._auth,
                timeout=self.DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except requests.HTTPError as exc:
            raise RazorpayError(str(exc)) from exc

    def retry_subscription_invoice(
        self,
        subscription_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Retry charging a subscription invoice."""
        headers = {
            "Idempotency-Key": idempotency_key,
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                f"{self.BASE_URL}/subscriptions/{subscription_id}/charge",
                auth=self._auth,
                headers=headers,
                timeout=self.DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except requests.HTTPError as exc:
            raise RazorpayError(str(exc)) from exc

