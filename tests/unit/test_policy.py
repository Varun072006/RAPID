"""
Unit tests for the policy engine.

Tests all 5 rules independently and at boundary conditions.
"""

from __future__ import annotations

import pytest

from packages.domain.policy.engine import MerchantPolicy, PolicyEngine


@pytest.fixture
def engine() -> PolicyEngine:
    return PolicyEngine(MerchantPolicy(
        max_auto_amount=25_000_00,
        max_retries=2,
        min_recovery_confidence=0.55,
        high_value_threshold=5_000_00,
    ))


class TestRule1UnknownStateGuard:
    """Rule 1: Never retry in UNKNOWN state."""

    def test_retry_now_in_unknown_state_denied(self, engine):
        authorized, reason = engine.authorize_action(
            action="retry_now",
            amount=10000,
            recovery_confidence=0.9,
            current_state="UNKNOWN",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is False
        assert "UNKNOWN" in reason

    def test_retry_later_in_unknown_state_denied(self, engine):
        authorized, reason = engine.authorize_action(
            action="retry_later",
            amount=10000,
            recovery_confidence=0.9,
            current_state="UNKNOWN",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is False

    def test_payment_link_in_unknown_state_allowed(self, engine):
        """Payment link does not involve retry — should be allowed."""
        authorized, reason = engine.authorize_action(
            action="payment_link",
            amount=10000,
            recovery_confidence=0.7,
            current_state="UNKNOWN",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is True


class TestRule2AmountLimit:
    def test_over_limit_denied(self, engine):
        authorized, reason = engine.authorize_action(
            action="retry_later",
            amount=30_000_00,  # ₹30,000 — over ₹25,000 limit
            recovery_confidence=0.9,
            current_state="FAILED",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is False
        assert "limit" in reason.lower() or "amount" in reason.lower()

    def test_at_limit_allowed(self, engine):
        authorized, _ = engine.authorize_action(
            action="retry_later",
            amount=25_000_00,  # exactly at limit
            recovery_confidence=0.9,
            current_state="FAILED",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is True


class TestRule3RetryCap:
    def test_at_max_retries_denied(self, engine):
        authorized, reason = engine.authorize_action(
            action="retry_now",
            amount=10000,
            recovery_confidence=0.9,
            current_state="FAILED",
            retry_count=2,  # at max
            system_healthy=True,
        )
        assert authorized is False

    def test_payment_link_not_subject_to_retry_cap(self, engine):
        """Payment link is not a retry — cap doesn't apply."""
        authorized, _ = engine.authorize_action(
            action="payment_link",
            amount=10000,
            recovery_confidence=0.7,
            current_state="FAILED",
            retry_count=5,  # way over cap
            system_healthy=True,
        )
        assert authorized is True


class TestRule4ConfidenceGate:
    def test_low_confidence_high_value_denied(self, engine):
        authorized, reason = engine.authorize_action(
            action="retry_later",
            amount=10_000_00,  # ₹10,000 — high value
            recovery_confidence=0.40,  # below 0.55 threshold
            current_state="FAILED",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is False
        assert "confidence" in reason.lower()

    def test_low_confidence_low_value_allowed(self, engine):
        """Low confidence is OK for low-value payments."""
        authorized, _ = engine.authorize_action(
            action="retry_later",
            amount=1_000,  # ₹10 — low value
            recovery_confidence=0.30,
            current_state="FAILED",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is True


class TestRule5IncidentGate:
    def test_retry_during_incident_denied(self, engine):
        authorized, reason = engine.authorize_action(
            action="retry_now",
            amount=10000,
            recovery_confidence=0.9,
            current_state="FAILED",
            retry_count=0,
            system_healthy=False,  # system unhealthy
        )
        assert authorized is False
        assert "incident" in reason.lower() or "system" in reason.lower()

    def test_payment_link_during_incident_allowed(self, engine):
        """Payment links don't stress the payment network."""
        authorized, _ = engine.authorize_action(
            action="payment_link",
            amount=10000,
            recovery_confidence=0.7,
            current_state="FAILED",
            retry_count=0,
            system_healthy=False,
        )
        assert authorized is True


class TestFullyAuthorized:
    def test_clean_case_fully_authorized(self, engine):
        """All rules pass — action authorized."""
        authorized, reason = engine.authorize_action(
            action="payment_link",
            amount=100000,  # ₹1,000
            recovery_confidence=0.75,
            current_state="FAILED",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is True
        assert reason == "AUTHORIZED"
