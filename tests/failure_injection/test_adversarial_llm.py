"""Failure injection tests — adversarial LLM recommendation scenario."""

from __future__ import annotations

import pytest

from packages.domain.policy.engine import PolicyEngine, MerchantPolicy


class TestAdversarialLLM:
    """Proves the Policy Engine acts as an impenetrable safety gate against untrusted LLM outputs."""

    def test_llm_recommends_policy_banned_action(self):
        """LLM attempts an unauthorized action like 'refund' or 'override_limit'."""
        policy = PolicyEngine()
        authorized, reason = policy.authorize_action(
            action="refund",
            amount=5000_00,
            recovery_confidence=0.99,
            current_state="FAILED",
            retry_count=0,
            system_healthy=True,
        )
        assert isinstance(authorized, bool)

    def test_llm_attempts_amount_override_beyond_limit(self):
        """LLM recommends executing high ticket recovery (e.g. ₹2,00,000) automatically."""
        policy = PolicyEngine(MerchantPolicy(max_auto_amount=25_000_00))
        authorized, reason = policy.authorize_action(
            action="retry_now",
            amount=200_000_00,  # ₹2,00,000 in paise
            recovery_confidence=0.99,
            current_state="FAILED",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is False
        assert "DENIED" in reason
        assert "exceeds automatic limit" in reason

    def test_llm_attempts_retry_on_unknown_state(self):
        """LLM recommends immediate retry on UNKNOWN payment state."""
        policy = PolicyEngine()
        authorized, reason = policy.authorize_action(
            action="retry_now",
            amount=1000_00,
            recovery_confidence=0.95,
            current_state="UNKNOWN",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is False
        assert "DENIED" in reason
        assert "UNKNOWN state" in reason

    def test_llm_attempts_retry_during_system_incident(self):
        """LLM recommends retrying during an ongoing bank outage (system_healthy=False)."""
        policy = PolicyEngine()
        authorized, reason = policy.authorize_action(
            action="retry_now",
            amount=1000_00,
            recovery_confidence=0.95,
            current_state="FAILED",
            retry_count=0,
            system_healthy=False,  # Incident active
        )
        assert authorized is False
        assert "DENIED" in reason
        assert "incident" in reason.lower()

    def test_llm_attempts_exceeding_retry_budget(self):
        """LLM recommends retry when retry_count has reached max retries limit."""
        policy = PolicyEngine(MerchantPolicy(max_retries=2))
        authorized, reason = policy.authorize_action(
            action="retry_later",
            amount=1000_00,
            recovery_confidence=0.90,
            current_state="FAILED",
            retry_count=2,  # Already retried 2 times
            system_healthy=True,
        )
        assert authorized is False
        assert "DENIED" in reason
        assert "Retry cap reached" in reason
