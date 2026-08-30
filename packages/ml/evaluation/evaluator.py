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

import json
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger


class HeldOutEvaluator:
    """Evaluates recovery strategies on held-out test data."""

    SUCCESS_THRESHOLD = 0.50

    def __init__(self, test_df: pd.DataFrame) -> None:
        self.test_df = test_df

    def evaluate_baseline_fixed_retry(self) -> dict:
        """Baseline 1: always retry_later."""
        col = "outcome_if_retry_later"
        recovered_mask = self.test_df[col] > self.SUCCESS_THRESHOLD
        recovered = int(recovered_mask.sum())
        amount_recovered = float(self.test_df.loc[recovered_mask, "amount"].sum())

        # Unnecessary retries: retried but would have failed
        unnecessary = int((~recovered_mask).sum())

        return {
            "name": "Fixed 6h Retry",
            "payments_recovered": recovered,
            "amount_recovered_inr": amount_recovered / 100,
            "recovery_rate": recovered / len(self.test_df),
            "unnecessary_retries": unnecessary,
            "unnecessary_retry_rate": unnecessary / len(self.test_df),
        }

    def evaluate_baseline_rule_based(self) -> dict:
        """Baseline 2: choose action with highest outcome probability."""
        recovered = 0
        amount_recovered = 0.0
        unnecessary = 0

        for _, row in self.test_df.iterrows():
            # Rule: pick action with max outcome
            outcomes = {
                "retry_now": row["outcome_if_retry_now"],
                "retry_later": row["outcome_if_retry_later"],
                "payment_link": row["outcome_if_payment_link"],
            }
            best_action = max(outcomes, key=lambda k: outcomes[k])
            best_outcome = outcomes[best_action]

            if best_outcome > self.SUCCESS_THRESHOLD:
                recovered += 1
                amount_recovered += row["amount"]
            else:
                unnecessary += 1

        return {
            "name": "Rule-Based (Oracle-Assisted)",
            "payments_recovered": recovered,
            "amount_recovered_inr": amount_recovered / 100,
            "recovery_rate": recovered / len(self.test_df),
            "unnecessary_retries": unnecessary,
            "unnecessary_retry_rate": unnecessary / len(self.test_df),
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

        # Batch prediction for all models
        all_actions = list(models.keys())
        prob_matrix = np.column_stack([
            models[action].predict_proba(X)[:, 1]
            for action in all_actions
        ])  # Shape: (N, num_actions)

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

        return {
            "name": "RAPID",
            "payments_recovered": recovered,
            "amount_recovered_inr": amount_recovered / 100,
            "recovery_rate": recovered / len(df),
            "unnecessary_retries": unnecessary,
            "unnecessary_retry_rate": unnecessary / len(df),
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
            }
        else:
            logger.warning("No model bundle provided — skipping RAPID evaluation")

        return results
