"""
Revenue optimizer — selects the best recovery action based on expected net value.

Formula:
    ENv(action) = P(recovery | action) × amount
                − cost(action)
                − friction_penalty(action) × amount
                − risk_penalty(action) × amount

The optimizer ranks all candidate actions and selects the one
with the highest expected net value (ENv).

This is NOT the same as selecting the action with the highest
recovery probability. An action with 90% recovery probability
might have lower ENv than one with 70% if the former has high
friction or cost.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class ActionEvaluation:
    """Result of evaluating one recovery action."""

    action: str
    recovery_prob: float
    expected_net_value: float  # in paise
    cost: float  # in paise
    friction_penalty: float  # in paise
    risk_penalty: float  # in paise
    gross_expected: float  # P × amount, before costs


# Action cost parameters (in paise, adjustable per merchant)
ACTION_PARAMS = {
    "retry_now": {
        "cost": 5,  # API call cost + processing
        "friction": 0.03,  # 3% friction (customer sees retry)
        "risk": 0.02,  # 2% risk (could hit rate limits)
    },
    "retry_later": {
        "cost": 5,
        "friction": 0.01,  # minimal friction (delayed, less visible)
        "risk": 0.01,  # lower risk (state might have resolved)
    },
    "payment_link": {
        "cost": 15,  # higher — SMS/email delivery cost
        "friction": 0.12,  # 12% friction (customer must take action)
        "risk": 0.00,  # no retry risk (fresh payment)
    },
    "do_nothing": {
        "cost": 0,
        "friction": 0.0,
        "risk": 0.0,
    },
}


class RevenueOptimizer:
    """
    Selects the recovery action that maximizes expected net revenue.

    This is the final decision maker in the RAPID pipeline.
    It ranks all actions by ENv and returns the best one.
    """

    def __init__(self, params: dict | None = None) -> None:
        self.params = params or ACTION_PARAMS

    def evaluate_action(
        self,
        action: str,
        recovery_prob: float,
        amount: int,  # in paise
    ) -> ActionEvaluation:
        """
        Calculate expected net value for one action.

        Args:
            action:        Action name (must be in ACTION_PARAMS).
            recovery_prob: P(success | action) from ML model.
            amount:        Payment amount in paise.

        Returns:
            ActionEvaluation with ENv breakdown.
        """
        p = self.params.get(action, self.params["do_nothing"])

        gross = recovery_prob * amount
        friction_penalty = p["friction"] * amount
        risk_penalty = p["risk"] * amount
        env = gross - p["cost"] - friction_penalty - risk_penalty

        return ActionEvaluation(
            action=action,
            recovery_prob=recovery_prob,
            expected_net_value=env,
            cost=p["cost"],
            friction_penalty=friction_penalty,
            risk_penalty=risk_penalty,
            gross_expected=gross,
        )

    def select_best_action(
        self,
        recovery_probs: dict[str, float],
        amount: int,
    ) -> tuple[str, list[ActionEvaluation]]:
        """
        Evaluate all actions and return the best one.

        Args:
            recovery_probs: Dict mapping action_name → P(success).
            amount:         Payment amount in paise.

        Returns:
            Tuple of (best_action_name, all_evaluations_sorted_by_env).
        """
        evaluations = [
            self.evaluate_action(action, prob, amount) for action, prob in recovery_probs.items()
        ]
        evaluations.sort(key=lambda e: e.expected_net_value, reverse=True)

        best = evaluations[0]
        logger.debug(
            f"Revenue optimizer: amount=₹{amount/100:.2f} "
            f"best={best.action} ENv=₹{best.expected_net_value/100:.2f} "
            f"P={best.recovery_prob:.2%}"
        )

        return best.action, evaluations
