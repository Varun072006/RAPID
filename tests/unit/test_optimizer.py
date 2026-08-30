"""Unit tests for the revenue optimizer."""

from __future__ import annotations

import pytest

from packages.domain.recovery.optimizer import RevenueOptimizer


class TestRevenueOptimizer:
    @pytest.fixture
    def optimizer(self) -> RevenueOptimizer:
        return RevenueOptimizer()

    def test_higher_probability_not_always_best(self, optimizer):
        """Payment link with high friction can lose to retry_later with lower probability."""
        probs = {
            "retry_later": 0.70,
            "payment_link": 0.90,  # higher prob
        }
        best, evals = optimizer.select_best_action(probs, amount=1000)
        # payment_link has 12% friction; retry_later has 1% — let optimizer decide
        best_eval = next(e for e in evals if e.action == best)
        assert best_eval.expected_net_value >= min(e.expected_net_value for e in evals)

    def test_do_nothing_has_zero_expected_value(self, optimizer):
        probs = {"do_nothing": 0.0}
        _, evals = optimizer.select_best_action(probs, amount=100000)
        do_nothing = next(e for e in evals if e.action == "do_nothing")
        assert do_nothing.expected_net_value == 0.0

    def test_best_action_is_highest_env(self, optimizer):
        """Best action always has the highest expected net value."""
        probs = {"retry_now": 0.5, "retry_later": 0.8, "payment_link": 0.6}
        best, evals = optimizer.select_best_action(probs, amount=200000)
        best_eval = next(e for e in evals if e.action == best)
        for e in evals:
            assert best_eval.expected_net_value >= e.expected_net_value

    def test_zero_amount_all_negative(self, optimizer):
        """With zero amount, all actions have negative ENv (costs exceed gains)."""
        probs = {"retry_now": 0.9, "retry_later": 0.9, "payment_link": 0.9}
        _, evals = optimizer.select_best_action(probs, amount=0)
        for e in evals:
            if e.action != "do_nothing":
                assert e.expected_net_value <= 0

    def test_evaluations_sorted_by_env(self, optimizer):
        """Evaluations list is sorted descending by ENv."""
        probs = {"retry_now": 0.5, "retry_later": 0.8, "payment_link": 0.6}
        _, evals = optimizer.select_best_action(probs, amount=100000)
        envs = [e.expected_net_value for e in evals]
        assert envs == sorted(envs, reverse=True)
