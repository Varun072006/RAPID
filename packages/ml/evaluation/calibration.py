"""
Model calibration evaluation.

A well-calibrated model produces meaningful probabilities:
- "80% confidence" → ~80% of such payments actually succeed
- This is essential for the revenue optimizer (which multiplies probability × amount)

Metrics:
- Brier score: mean squared error between predicted probabilities and outcomes
  (lower is better; < 0.25 is acceptable; < 0.10 is excellent)
- Calibration curve: plots predicted vs actual probabilities per decile
"""

from __future__ import annotations

import numpy as np
from sklearn.calibration import calibration_curve


def evaluate_calibration(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    n_bins: int = 10,
    action_name: str = "",
) -> dict:
    """
    Evaluate probability calibration quality.

    Args:
        y_true:       Binary ground truth (0 or 1).
        y_pred_proba: Predicted probabilities [0, 1].
        n_bins:       Number of bins for calibration curve.
        action_name:  Label for logging.

    Returns:
        Dict with brier_score, prob_true, prob_pred, max_calibration_error.
    """
    prob_true, prob_pred = calibration_curve(
        y_true, y_pred_proba, n_bins=n_bins, strategy="uniform"
    )

    # Brier score: MSE of probabilities
    brier = float(np.mean((y_pred_proba - y_true) ** 2))

    # Expected Calibration Error (ECE): weighted mean |predicted - actual|
    bin_sizes = np.histogram(y_pred_proba, bins=n_bins, range=(0, 1))[0]
    ece = float(
        np.sum(
            np.abs(prob_true - prob_pred) * bin_sizes[: len(prob_true)]
        )
        / len(y_true)
    )

    max_err = float(np.max(np.abs(prob_true - prob_pred))) if len(prob_true) > 0 else 0.0

    quality = (
        "excellent" if brier < 0.10 else
        "good" if brier < 0.20 else
        "acceptable" if brier < 0.25 else
        "poor"
    )

    label = f"[{action_name}] " if action_name else ""
    from loguru import logger
    logger.info(
        f"{label}Calibration: Brier={brier:.4f} ECE={ece:.4f} "
        f"MaxErr={max_err:.4f} Quality={quality}"
    )

    return {
        "action": action_name,
        "brier_score": brier,
        "ece": ece,
        "max_calibration_error": max_err,
        "quality": quality,
        "prob_true": prob_true.tolist(),
        "prob_pred": prob_pred.tolist(),
    }
