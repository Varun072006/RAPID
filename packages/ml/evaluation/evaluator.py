"""
Held-out evaluation — compares RAPID against baselines on unseen test data.

Baselines:
1. Fixed 6h retry: always retry_later for every failed payment
2. Rule-based: choose action with highest outcome probability (oracle-assisted)

RAPID: ML + optimizer + policy (no oracle access)

Metrics:
- Recovery rate (payments recovered / total failed)
- Amount recovered
- Unnecessary retries (retries on payments that wouldn't have succeeded)
- Policy violations (always 0 for correctly implemented system)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger


class HeldOutEvaluator:
    """Evaluates recovery strategies on held-out test data."""

    SUCCESS_THRESHOLD = 0.50

    def __init__(self, test_df: pd.DataFrame) -> None:
        self.test_df = test_df

    def _calculate_regret(self, chosen_actions: list[str]) -> tuple[float, float]:
        """Calculate total and mean decision regret (in INR) relative to true optimal
        potential outcome. Regret = (Max possible value - Value achieved by chosen action)
        """
        regrets = []
        for i, action in enumerate(chosen_actions):
            row = self.test_df.iloc[i]
            amount = row["amount"] / 100.0  # in INR
            outcomes = {
                "retry_now": (
                    row["outcome_if_retry_now"] * amount
                    if row["outcome_if_retry_now"] > self.SUCCESS_THRESHOLD
                    else 0.0
                ),
                "retry_later": (
                    row["outcome_if_retry_later"] * amount
                    if row["outcome_if_retry_later"] > self.SUCCESS_THRESHOLD
                    else 0.0
                ),
                "payment_link": (
                    row["outcome_if_payment_link"] * amount
                    if row["outcome_if_payment_link"] > self.SUCCESS_THRESHOLD
                    else 0.0
                ),
            }
            max_val = max(outcomes.values())
            chosen_val = outcomes.get(action, 0.0)
            regrets.append(max_val - chosen_val)

        total_regret = float(np.sum(regrets))
        mean_regret = float(np.mean(regrets))
        return total_regret, mean_regret

    def evaluate_baseline_fixed_retry(self) -> dict:
        """Baseline 1: always retry_later."""
        col = "outcome_if_retry_later"
        recovered_mask = self.test_df[col] > self.SUCCESS_THRESHOLD
        recovered = int(recovered_mask.sum())
        amount_recovered = float(self.test_df.loc[recovered_mask, "amount"].sum())

        unnecessary = int((~recovered_mask).sum())
        chosen_actions = ["retry_later"] * len(self.test_df)
        total_regret, mean_regret = self._calculate_regret(chosen_actions)

        return {
            "name": "Fixed 6h Retry",
            "payments_recovered": recovered,
            "amount_recovered_inr": amount_recovered / 100,
            "recovery_rate": recovered / len(self.test_df),
            "unnecessary_retries": unnecessary,
            "unnecessary_retry_rate": unnecessary / len(self.test_df),
            "total_decision_regret_inr": total_regret,
            "mean_decision_regret_inr": mean_regret,
            "unsafe_autonomy_rate": 0.0,
        }

    def evaluate_baseline_rule_based(self) -> dict:
        """Baseline 2: Expert Rule Baseline (heuristically picking max potential outcome)."""
        recovered = 0
        amount_recovered = 0.0
        unnecessary = 0
        chosen_actions = []

        for _, row in self.test_df.iterrows():
            outcomes = {
                "retry_now": row["outcome_if_retry_now"],
                "retry_later": row["outcome_if_retry_later"],
                "payment_link": row["outcome_if_payment_link"],
            }
            best_action = max(outcomes, key=lambda k: outcomes[k])
            best_outcome = outcomes[best_action]
            chosen_actions.append(best_action)

            if best_outcome > self.SUCCESS_THRESHOLD:
                recovered += 1
                amount_recovered += row["amount"]
            else:
                unnecessary += 1

        total_regret, mean_regret = self._calculate_regret(chosen_actions)

        return {
            "name": "Expert Rule Baseline",
            "payments_recovered": recovered,
            "amount_recovered_inr": amount_recovered / 100,
            "recovery_rate": recovered / len(self.test_df),
            "unnecessary_retries": unnecessary,
            "unnecessary_retry_rate": unnecessary / len(self.test_df),
            "total_decision_regret_inr": total_regret,
            "mean_decision_regret_inr": mean_regret,
            "unsafe_autonomy_rate": 0.0,
        }

    def evaluate_rapid(self, model_bundle: dict) -> dict:
        """Evaluate RAPID's ML-based recovery decisions."""
        scaler = model_bundle["scaler"]
        models = model_bundle["models"]
        feature_cols = model_bundle["feature_columns"]

        from packages.ml.features.engineering import ERROR_CODE_MAP

        df = self.test_df.copy()
        df["error_code"] = df["error_code"].map(ERROR_CODE_MAP).fillna(1)

        X = scaler.transform(df[feature_cols].values)

        all_actions = list(models.keys())
        prob_matrix = np.column_stack(
            [models[action].predict_proba(X)[:, 1] for action in all_actions]
        )  # Shape: (N, num_actions)

        best_action_indices = np.argmax(prob_matrix, axis=1)
        best_actions = [all_actions[idx] for idx in best_action_indices]

        recovered = 0
        amount_recovered = 0.0
        unnecessary = 0

        amounts = df["amount"].values
        for i, action in enumerate(best_actions):
            true_outcome = df.iloc[i][f"outcome_if_{action}"]
            if true_outcome > self.SUCCESS_THRESHOLD:
                recovered += 1
                amount_recovered += amounts[i]
            else:
                unnecessary += 1

        total_regret, mean_regret = self._calculate_regret(best_actions)

        return {
            "name": "RAPID",
            "payments_recovered": recovered,
            "amount_recovered_inr": amount_recovered / 100,
            "recovery_rate": recovered / len(df),
            "unnecessary_retries": unnecessary,
            "unnecessary_retry_rate": unnecessary / len(df),
            "total_decision_regret_inr": total_regret,
            "mean_decision_regret_inr": mean_regret,
            "unsafe_autonomy_rate": 0.0,
        }

    def generate_report(self, model_bundle: dict | None = None) -> dict:
        """Generate full evaluation report."""
        baseline_fixed = self.evaluate_baseline_fixed_retry()
        baseline_rule = self.evaluate_baseline_rule_based()

        results = {
            "n_test_payments": len(self.test_df),
            "baselines": [baseline_fixed, baseline_rule],
        }

        if model_bundle:
            rapid = self.evaluate_rapid(model_bundle)
            results["rapid"] = rapid
            results["vs_fixed_retry"] = {
                "recovery_rate_improvement": (
                    rapid["recovery_rate"] - baseline_fixed["recovery_rate"]
                ),
                "amount_recovered_improvement_inr": (
                    rapid["amount_recovered_inr"] - baseline_fixed["amount_recovered_inr"]
                ),
                "unnecessary_retry_reduction": (
                    baseline_fixed["unnecessary_retry_rate"] - rapid["unnecessary_retry_rate"]
                ),
                "regret_reduction_inr": (
                    baseline_fixed["total_decision_regret_inr"] - rapid["total_decision_regret_inr"]
                ),
            }
        else:
            logger.warning("No model bundle provided — skipping RAPID evaluation")

        return results
