"""
Recovery outcome model training — one model per action.

For each recovery action (retry_now, retry_later, payment_link), we train
a separate logistic regression model to predict P(success | action, context).

Why separate models per action?
- Simpler to debug: each model has one job
- Independent calibration: errors in one don't affect others
- Interpretable: feature importance is action-specific
- Easy to A/B test individual models

Calibration note:
    We use CalibratedClassifierCV to ensure predicted probabilities are
    meaningful. If model says 80%, ~80% of those payments should actually
    succeed with that action.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from loguru import logger
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

from packages.ml.features.engineering import ERROR_CODE_MAP, FEATURE_COLUMNS
from packages.ml.simulation.scenario_generator import ScenarioGenerator

ACTIONS = ["retry_now", "retry_later", "payment_link"]
SUCCESS_THRESHOLD = 0.50  # outcome_prob > 0.5 → "would have succeeded"


def train(
    data_dir: str = "packages/ml/simulation",
    output_dir: str = "packages/ml/models",
) -> dict[str, Any]:
    """
    Train three recovery models (one per action) + a shared scaler.

    Returns model bundle dict.
    """
    logger.info("Loading training data for recovery models...")
    train_df = ScenarioGenerator.load("train", data_dir)
    val_df = ScenarioGenerator.load("validation", data_dir)

    # Encode error_code
    for df in [train_df, val_df]:
        df["error_code"] = df["error_code"].map(ERROR_CODE_MAP).fillna(1)

    X_train = train_df[FEATURE_COLUMNS].values
    X_val = val_df[FEATURE_COLUMNS].values

    # Fit shared scaler on train only
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)

    model_bundle: dict[str, Any] = {
        "scaler": scaler,
        "feature_columns": FEATURE_COLUMNS,
        "models": {},
    }

    for action in ACTIONS:
        label_col = f"outcome_if_{action}"

        # Binary label: would this action have succeeded?
        y_train = (train_df[label_col] > SUCCESS_THRESHOLD).astype(int)
        y_val = (val_df[label_col] > SUCCESS_THRESHOLD).astype(int)

        logger.info(
            f"Training recovery model for '{action}': "
            f"{y_train.sum():,}/{len(y_train):,} positive examples "
            f"({100 * y_train.mean():.1f}% success rate)"
        )

        # Logistic Regression with calibration
        base_model = LogisticRegression(
            max_iter=1000,
            C=1.0,
            solver="lbfgs",
            random_state=42,
        )
        calibrated = CalibratedClassifierCV(base_model, cv=5, method="isotonic")
        calibrated.fit(X_train_scaled, y_train)

        # Evaluate on validation
        val_proba = calibrated.predict_proba(X_val_scaled)[:, 1]
        auc = roc_auc_score(y_val, val_proba)
        brier = brier_score_loss(y_val, val_proba)

        logger.info(
            f"  [{action}] val AUC={auc:.4f}  Brier={brier:.4f}  "
            f"(Brier < 0.25 = good calibration)"
        )

        model_bundle["models"][action] = calibrated

    # Save bundle
    output_path = Path(output_dir) / "recovery_models.pkl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(model_bundle, f)

    logger.info(f"Recovery models saved → {output_path}")
    return model_bundle


if __name__ == "__main__":
    train()
