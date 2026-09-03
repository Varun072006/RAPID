"""
Scenario generator — produces 100K synthetic payment scenarios.

Each scenario contains:
- Observable features (input to ML models)
- Counterfactual outcomes for each action (training labels)
- Hidden factors (for analysis only — never given to the model)
- Split assignment (train/val/test/distribution_shift)

Distribution-shift split simulates a world where bank failure rates
have increased 1.5x — used to test model robustness.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from packages.ml.simulation.causal_model import CausalPaymentModel


class ScenarioGenerator:
    """
    Generates reproducible synthetic payment scenarios.

    Split proportions:
    - train:              60%  (model training)
    - validation:         20%  (hyperparameter tuning)
    - test:               10%  (held-out evaluation)
    - distribution_shift: 10%  (robustness test)
    """

    SPLIT_BOUNDARIES = {
        "train": (0, 60),
        "validation": (60, 80),
        "test": (80, 90),
        "distribution_shift": (90, 100),
    }

    # Degradation factors applied to distribution_shift scenarios
    SHIFT_DEGRADATION = {
        "retry_now": 0.60,
        "retry_later": 0.60,
        "payment_link": 0.75,
    }

    def __init__(self, seed: int = 42, n_scenarios: int = 100_000) -> None:
        self.seed = seed
        self.n_scenarios = n_scenarios
        self.model = CausalPaymentModel(seed=seed)

    def _assign_split(self, idx: int) -> str:
        bucket = idx % 100
        for split, (lo, hi) in self.SPLIT_BOUNDARIES.items():
            if lo <= bucket < hi:
                return split
        return "train"

    def generate(self) -> dict[str, pd.DataFrame]:
        """
        Generate all scenarios and return as a dict of DataFrames.

        Returns:
            {
                "train": DataFrame,
                "validation": DataFrame,
                "test": DataFrame,
                "distribution_shift": DataFrame,
            }
        """
        logger.info(f"Generating {self.n_scenarios:,} scenarios (seed={self.seed})...")

        rows = []
        for i in range(self.n_scenarios):
            split = self._assign_split(i)
            hidden = self.model.generate_hidden_factors()
            features = self.model.generate_observable_features(hidden)

            # Counterfactual outcomes
            retry_now = self.model.outcome_if_retry_now(hidden, customer_retry_count=0)
            retry_later = self.model.outcome_if_retry_later(hidden, customer_retry_count=0)
            payment_link = self.model.outcome_if_payment_link(hidden)

            # Apply degradation to distribution_shift scenarios
            if split == "distribution_shift":
                retry_now *= self.SHIFT_DEGRADATION["retry_now"]
                retry_later *= self.SHIFT_DEGRADATION["retry_later"]
                payment_link *= self.SHIFT_DEGRADATION["payment_link"]
                # Also degrade observable features to reflect environment shift
                features["error_code"] = "ISSUER_TIMEOUT"
                features["latency_ms"] = min(features["latency_ms"] * 2.5, 8000)

            row = {
                "scenario_id": i,
                "split": split,
                **features,
                # Action outcomes (labels for supervised learning)
                "outcome_if_retry_now": float(np.clip(retry_now, 0, 1)),
                "outcome_if_retry_later": float(np.clip(retry_later, 0, 1)),
                "outcome_if_payment_link": float(np.clip(payment_link, 0, 1)),
                # Hidden factors (for analysis/debugging only)
                "_hidden_issuer_health": hidden.issuer_health,
                "_hidden_network_quality": hidden.network_quality,
                "_hidden_customer_liquidity": hidden.customer_liquidity,
                "_hidden_customer_intent": hidden.customer_intent,
                "_hidden_payment_persistence": hidden.payment_persistence,
            }
            rows.append(row)

            if (i + 1) % 10_000 == 0:
                logger.info(f"  Generated {i + 1:,} / {self.n_scenarios:,} scenarios")

        df = pd.DataFrame(rows)
        splits = {
            name: df[df["split"] == name].drop(columns=["split"]).reset_index(drop=True)
            for name in ["train", "validation", "test", "distribution_shift"]
        }

        for name, sdf in splits.items():
            logger.info(f"  {name}: {len(sdf):,} scenarios")

        return splits

    def save(self, output_dir: str | Path = "packages/ml/simulation") -> None:
        """Generate and save all splits as Parquet files."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        splits = self.generate()
        for name, df in splits.items():
            path = output_dir / f"{name}.parquet"
            df.to_parquet(path, index=False)
            logger.info(f"Saved {name} split → {path} ({len(df):,} rows)")

    @staticmethod
    def load(
        split: str,
        data_dir: str | Path = "packages/ml/simulation",
    ) -> pd.DataFrame:
        """Load a previously saved split."""
        path = Path(data_dir) / f"{split}.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"Split '{split}' not found at {path}. " f"Run: python scripts/generate-data.py"
            )
        return pd.read_parquet(path)
