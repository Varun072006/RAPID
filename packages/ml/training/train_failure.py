"""
Failure classifier training — predicts failure mode from observable features.

Failure modes:
- transient:               Issuer/network blip — retry likely helps
- customer_action_needed:  Customer must intervene (link, manual retry)
- infrastructure:          System-wide degradation — pause retries
- customer_issue:          Insufficient funds or fraud — retries unlikely to help

The classifier is trained on inferred labels (derived from counterfactual
outcomes), NOT ground-truth hidden factors. This is the circular evaluation
caveat documented in evaluation.md.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
from loguru import logger
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report

from packages.ml.features.engineering import FEATURE_COLUMNS
from packages.ml.simulation.scenario_generator import ScenarioGenerator


def infer_failure_mode(row: pd.Series) -> str:
    """
    Infer failure mode from counterfactual outcomes.

    Rules (deterministic labelling from causal structure):
    - high retry_now → transient (retry immediately helps)
    - low retry_now + high payment_link → customer_action_needed
    - high retry_later but low retry_now → infrastructure (needs time)
    - all low → customer_issue (structural, retries unlikely to help)
    """
    rn = row["outcome_if_retry_now"]
    rl = row["outcome_if_retry_later"]
    pl = row["outcome_if_payment_link"]

    if rn > 0.65:
        return "transient"
    elif pl > rn and pl > 0.55:
        return "customer_action_needed"
    elif rl > rn + 0.15:
        return "infrastructure"
    else:
        return "customer_issue"


def train(
    data_dir: str = "packages/ml/simulation",
    output_dir: str = "packages/ml/models",
) -> GradientBoostingClassifier:
    """
    Train failure classifier on training split.

    Evaluates on validation split and prints classification report.
    """
    logger.info("Loading training data...")
    train_df = ScenarioGenerator.load("train", data_dir)
    val_df = ScenarioGenerator.load("validation", data_dir)

    # Encode error_code (string) to int
    from packages.ml.features.engineering import ERROR_CODE_MAP

    for df in [train_df, val_df]:
        df["error_code"] = df["error_code"].map(ERROR_CODE_MAP).fillna(1)

    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df.apply(infer_failure_mode, axis=1)

    X_val = val_df[FEATURE_COLUMNS]
    y_val = val_df.apply(infer_failure_mode, axis=1)

    logger.info(f"Training failure classifier on {len(train_df):,} examples...")
    logger.info(f"Label distribution:\n{y_train.value_counts()}")

    clf = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )
    clf.fit(X_train, y_train)

    val_preds = clf.predict(X_val)
    logger.info(f"Validation results:\n" f"{classification_report(y_val, val_preds)}")

    # Save model
    output_path = Path(output_dir) / "failure_classifier.pkl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(clf, f)

    logger.info(f"Failure classifier saved → {output_path}")
    return clf


if __name__ == "__main__":
    train()
