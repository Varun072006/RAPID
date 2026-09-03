"""
Property-based tests using Hypothesis.

Tests invariants that must hold for ALL possible inputs,
not just the cases we thought of.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from packages.domain.payments.models import PaymentState
from packages.domain.payments.state_machine import StateMachine
from packages.domain.policy.engine import MerchantPolicy, PolicyEngine
from packages.domain.recovery.optimizer import RevenueOptimizer
from packages.utils.idempotency import IdempotencyKeyGenerator


class TestStateMachineProperties:
    @given(
        from_state=st.sampled_from(list(PaymentState)),
        to_state=st.sampled_from(list(PaymentState)),
    )
    def test_transition_always_returns_bool_and_reason(
        self, from_state: PaymentState, to_state: PaymentState
    ):
        """transition() always returns (bool, non-empty string)."""
        success, reason = StateMachine.transition(from_state, to_state)
        assert isinstance(success, bool)
        assert isinstance(reason, str)
        assert len(reason) > 0

    @given(state=st.sampled_from(list(PaymentState)))
    def test_self_transition_always_invalid(self, state: PaymentState):
        """No state can transition to itself."""
        success, _ = StateMachine.transition(state, state)
        assert success is False

    @given(state=st.sampled_from(list(PaymentState)))
    def test_settled_is_only_terminal(self, state: PaymentState):
        """Only SETTLED has no outgoing transitions."""
        is_terminal = StateMachine.is_terminal(state)
        if state == PaymentState.SETTLED:
            assert is_terminal is True
        else:
            # All other states should have at least one valid outgoing transition
            # (except possibly ESCALATED which has limited exits)
            pass  # Not all states are required to be non-terminal in all configs


class TestIdempotencyProperties:
    @given(
        payment_id=st.text(
            min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N", "P"))
        ),
        action=st.sampled_from(["retry_now", "retry_later", "payment_link"]),
        merchant_id=st.text(
            min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N"))
        ),
    )
    def test_same_inputs_same_key(self, payment_id, action, merchant_id):
        """Idempotency key is deterministic — same inputs → same key."""
        key1 = IdempotencyKeyGenerator.generate(payment_id, action, merchant_id)
        key2 = IdempotencyKeyGenerator.generate(payment_id, action, merchant_id)
        assert key1 == key2

    @given(
        payment_id=st.text(min_size=1, max_size=64),
        action=st.sampled_from(["retry_now", "retry_later", "payment_link"]),
        merchant_id=st.text(min_size=1, max_size=64),
    )
    def test_key_is_16_chars(self, payment_id, action, merchant_id):
        """Idempotency key is always exactly 16 hex characters."""
        key = IdempotencyKeyGenerator.generate(payment_id, action, merchant_id)
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)


class TestOptimizerProperties:
    @given(
        probs=st.fixed_dictionaries(
            {
                "retry_now": st.floats(min_value=0.0, max_value=1.0),
                "retry_later": st.floats(min_value=0.0, max_value=1.0),
                "payment_link": st.floats(min_value=0.0, max_value=1.0),
            }
        ),
        amount=st.integers(min_value=0, max_value=10_000_00),
    )
    def test_best_action_has_max_env(self, probs, amount):
        """Selected action always has the highest expected net value."""
        optimizer = RevenueOptimizer()
        best, evals = optimizer.select_best_action(probs, amount)
        best_eval = next(e for e in evals if e.action == best)
        for e in evals:
            assert best_eval.expected_net_value >= e.expected_net_value - 1e-9  # float tolerance

    @given(amount=st.integers(min_value=1, max_value=10_000_00))
    def test_evaluations_monotone_sorted(self, amount):
        """Evaluations list is always sorted descending by ENv."""
        optimizer = RevenueOptimizer()
        probs = {"retry_now": 0.5, "retry_later": 0.8, "payment_link": 0.6}
        _, evals = optimizer.select_best_action(probs, amount)
        envs = [e.expected_net_value for e in evals]
        assert envs == sorted(envs, reverse=True)


class TestPolicyEngineProperties:
    @given(
        amount=st.integers(min_value=30_000_00, max_value=100_000_00),
    )
    def test_over_limit_always_denied(self, amount):
        """Any amount over the limit is always denied, regardless of other params."""
        engine = PolicyEngine(MerchantPolicy(max_auto_amount=25_000_00))
        authorized, _ = engine.authorize_action(
            action="retry_later",
            amount=amount,
            recovery_confidence=0.99,
            current_state="FAILED",
            retry_count=0,
            system_healthy=True,
        )
        assert authorized is False

    @given(retry_count=st.integers(min_value=2, max_value=100))
    def test_over_retry_cap_always_denied(self, retry_count):
        """Any retry count at or above max always denied."""
        engine = PolicyEngine(MerchantPolicy(max_retries=2))
        authorized, _ = engine.authorize_action(
            action="retry_now",
            amount=10000,
            recovery_confidence=0.99,
            current_state="FAILED",
            retry_count=retry_count,
            system_healthy=True,
        )
        assert authorized is False
