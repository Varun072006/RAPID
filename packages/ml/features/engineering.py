"""
Feature engineering — maps Payment ORM objects to ML feature vectors.

All feature extraction logic lives here to ensure consistency between
training (from Parquet) and inference (from live DB objects).
"""

from __future__ import annotations

from typing import Any

ERROR_CODE_MAP = {
    "SUCCESS": 0,
    "AUTHORIZATION_FAILED": 1,
    "ISSUER_TIMEOUT": 2,
    "INSUFFICIENT_FUNDS": 3,
    "BAD_REQUEST_ERROR": 4,
}

PAYMENT_METHOD_MAP = {
    "card": 0,
    "upi": 1,
    "netbanking": 2,
    "wallet": 3,
}

FEATURE_COLUMNS = [
    "amount",
    "payment_method",
    "bank",
    "latency_ms",
    "error_code",
    "customer_days_active",
    "customer_success_rate",
    "customer_churn_risk",
]


def extract_features(payment: dict[str, Any]) -> dict[str, float]:
    """
    Extract ML features from a payment dict (from DB or simulation).

    Args:
        payment: Dict with payment attributes.

    Returns:
        Feature dict ready for sklearn models.
    """
    return {
        "amount": float(payment.get("amount", 0)),
        "payment_method": PAYMENT_METHOD_MAP.get(str(payment.get("payment_method", "card")), 0),
        "bank": int(payment.get("bank", 0)),
        "latency_ms": float(payment.get("latency_ms", 500)),
        "error_code": ERROR_CODE_MAP.get(str(payment.get("error_code", "AUTHORIZATION_FAILED")), 1),
        "customer_days_active": float(payment.get("customer_days_active", 30)),
        "customer_success_rate": float(payment.get("customer_success_rate", 0.5)),
        "customer_churn_risk": float(payment.get("customer_churn_risk", 0.3)),
    }


def features_to_array(features: dict[str, float]) -> list[float]:
    """Convert feature dict to ordered list (for sklearn)."""
    return [features[col] for col in FEATURE_COLUMNS]
