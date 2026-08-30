"""
Policy engine — deterministic authorization gate for all recovery actions.

Design principle:
    LLM proposes. Policy engine authorizes. No exceptions.

The policy engine is the last safety check before any action is executed.
It is fully deterministic — no ML, no probabilities. Every rule has a clear
rationale and is independently testable.

Rules (evaluated in order, first DENY terminates):
1. Unknown-state guard: never retry UNKNOWN state (double-charge risk)
2. Amount limit: automatic actions capped at merchant's max_auto_amount
3. Retry cap: maximum N retries per payment
4. Confidence gate: low-confidence predictions on high-value payments
5. Incident gate: system health → pause retries during incidents
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class MerchantPolicy:
    """
    Per-merchant policy configuration.

    In production this would be fetched from a merchant config service.
    For the buildathon, a single global policy is used.
    """

    max_auto_amount: int = 25_000_00     # ₹25,000 in paise
    max_retries: int = 2                 # per payment
    min_recovery_confidence: float = 0.55
    high_value_threshold: int = 5_000_00 # ₹5,000 — apply stricter checks
    unknown_state_retry: bool = False    # MUST remain False


# Default policy (override per merchant)
DEFAULT_POLICY = MerchantPolicy()


class PolicyDenied(Exception):
    """Raised when a policy check rejects an action."""


class PolicyEngine:
    """
    Deterministic policy evaluation for recovery actions.

    All rules return (authorized: bool, reason: str).
    Caller must check authorized before proceeding.
    """

    def __init__(self, policy: MerchantPolicy | None = None) -> None:
        self.policy = policy or DEFAULT_POLICY

    def authorize_action(
        self,
        action: str,
        amount: int,               # in paise
        recovery_confidence: float,
        current_state: str,
        retry_count: int,
        system_healthy: bool,
    ) -> tuple[bool, str]:
        """
        Evaluate whether an action is permitted under current policy.

        Args:
            action:               Proposed action (e.g. retry_later, payment_link)
            amount:               Payment amount in paise
            recovery_confidence:  ML model's P(success) for this action
            current_state:        Current payment state string
            retry_count:          Number of times this payment has been retried
            system_healthy:       False if HealthDetector reports INCIDENT

        Returns:
            (True, "AUTHORIZED")        — proceed
            (False, reason: str)        — deny with reason
        """
        # ── Rule 1: Unknown-state guard (CRITICAL SAFETY RULE) ──────────
        if current_state == "UNKNOWN" and "retry" in action.lower():
            reason = (
                "DENIED: Cannot retry a payment in UNKNOWN state. "
                "Risk of double-charge. Reconcile with Razorpay first."
            )
            logger.warning(f"Policy DENIED [{action}]: {reason}")
            return False, reason

        # ── Rule 2: Amount limit ─────────────────────────────────────────
        if amount > self.policy.max_auto_amount:
            reason = (
                f"DENIED: Amount ₹{amount/100:.2f} exceeds automatic limit "
                f"₹{self.policy.max_auto_amount/100:.2f}. Requires human review."
            )
            logger.warning(f"Policy DENIED [{action}]: {reason}")
            return False, reason

        # ── Rule 3: Retry cap ─────────────────────────────────────────────
        is_retry = "retry" in action.lower()
        if is_retry and retry_count >= self.policy.max_retries:
            reason = (
                f"DENIED: Retry cap reached ({retry_count}/{self.policy.max_retries}). "
                f"Escalating to payment link or human review."
            )
            logger.warning(f"Policy DENIED [{action}]: {reason}")
            return False, reason

        # ── Rule 4: Confidence gate (high-value only) ─────────────────────
        is_high_value = amount >= self.policy.high_value_threshold
        if (
            is_high_value
            and recovery_confidence < self.policy.min_recovery_confidence
        ):
            reason = (
                f"DENIED: Low confidence ({recovery_confidence:.0%}) "
                f"on high-value payment (₹{amount/100:.2f}). "
                f"Minimum required: {self.policy.min_recovery_confidence:.0%}."
            )
            logger.warning(f"Policy DENIED [{action}]: {reason}")
            return False, reason

        # ── Rule 5: Incident gate ─────────────────────────────────────────
        if not system_healthy and is_retry:
            reason = (
                "DENIED: System incident detected. "
                "Automatic retries paused to avoid thrashing degraded infrastructure."
            )
            logger.warning(f"Policy DENIED [{action}]: {reason}")
            return False, reason

        logger.info(
            f"Policy AUTHORIZED [{action}]: "
            f"amount=₹{amount/100:.2f} "
            f"confidence={recovery_confidence:.0%} "
            f"retries={retry_count}/{self.policy.max_retries}"
        )
        return True, "AUTHORIZED"
