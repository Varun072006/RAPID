"""
Idempotency key generator — ensures recovery actions are never executed twice.

A stable, deterministic key derived from (merchant_id, payment_id, action_type)
means that even if the orchestrator crashes and restarts mid-execution,
the same API call will be deduplicated by Razorpay's idempotency layer.

Property: same inputs → same key, always.
"""

from __future__ import annotations

import hashlib


class IdempotencyKeyGenerator:
    """
    Generates deterministic idempotency keys for Razorpay API calls.

    Usage:
        key = IdempotencyKeyGenerator.generate("pay_001", "payment_link", "merchant_xyz")
        # → "a3f8c2d1e9b7"  (stable for these inputs)
    """

    @staticmethod
    def generate(
        payment_id: str,
        action_type: str,
        merchant_id: str,
    ) -> str:
        """
        Generate a stable idempotency key.

        Inputs are sorted deterministically before hashing to ensure
        the key is consistent regardless of call order.

        Returns a 16-character hex string (sufficiently unique for our scale).
        """
        # Canonical form: sort components to ensure determinism
        canonical = f"{merchant_id}:{payment_id}:{action_type}"
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return digest[:16]

    @staticmethod
    def generate_with_attempt(
        payment_id: str,
        action_type: str,
        merchant_id: str,
        attempt: int = 0,
    ) -> str:
        """
        Generate a key that is unique per attempt number.

        Use when you intentionally want a new idempotency key
        (e.g., after reconciliation confirms the previous attempt failed).
        """
        canonical = f"{merchant_id}:{payment_id}:{action_type}:{attempt}"
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return digest[:16]
