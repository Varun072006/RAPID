"""
Causal payment model — generates synthetic scenarios with real causal structure.

This is NOT the ML model used for prediction.
This is the simulated world that generates training data.

Why causal structure matters:
- Real-world payment failures have HIDDEN causes (issuer health, network quality)
- Observable features (latency, error codes) are noisy proxies for hidden causes
- ML models must learn to predict outcomes from observable proxies
- Without causal structure, synthetic data is trivial to overfit and meaningless

The causal graph:
    HiddenFactors → ObservableFeatures
    HiddenFactors → ActionOutcomes

The ML model sees only ObservableFeatures → predicts ActionOutcomes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class HiddenFactors:
    """
    Real-world causal factors hidden from the prediction model.
    Used only to generate ground-truth outcomes.

    All values are in [0, 1] where 1 is the best possible state.
    """

    issuer_health: float       # 0=full incident, 1=fully healthy
    network_quality: float     # 0=severe packet loss, 1=perfect
    customer_liquidity: float  # 0=insufficient funds, 1=ample funds
    customer_intent: float     # 0=likely fraud/abandon, 1=genuine buyer
    payment_persistence: float # 0=will abandon on friction, 1=will retry
    system_load: float         # 0=overloaded, 1=normal load


class CausalPaymentModel:
    """
    Causal simulator — generates synthetic payment scenarios.

    Each scenario has:
    - Hidden causal factors (drawn from calibrated distributions)
    - Observable features (noisy proxies for hidden factors)
    - Counterfactual outcomes for each possible action

    Counterfactual outcomes represent: "what would have happened
    if we had taken action X?" — enabling training of action-specific models.
    """

    def __init__(self, seed: int = 42) -> None:
        self.rng = np.random.default_rng(seed)

    def generate_hidden_factors(self) -> HiddenFactors:
        """
        Sample hidden causal factors from calibrated Beta distributions.

        Beta distributions are used because:
        - They are bounded [0, 1]
        - They can be skewed to reflect real-world priors
          (e.g., most issuers are healthy most of the time)
        """
        return HiddenFactors(
            issuer_health=float(self.rng.beta(8, 2)),       # mostly healthy
            network_quality=float(self.rng.beta(7, 2)),     # mostly good
            customer_liquidity=float(self.rng.beta(7, 2)),  # mostly funded
            customer_intent=float(self.rng.beta(8, 1.5)),   # mostly genuine
            payment_persistence=float(self.rng.beta(6, 3)), # moderately persistent
            system_load=float(self.rng.beta(8, 2)),         # mostly normal
        )

    def outcome_if_retry_now(
        self,
        hidden: HiddenFactors,
        customer_retry_count: int = 0,
    ) -> float:
        """
        P(success | retry_immediately, hidden_factors).

        Immediate retry works well for transient issues but has retry fatigue
        and may hit the same degraded infrastructure window.
        """
        base = 0.85
        prob = (
            base
            * hidden.issuer_health        # issuer must be healthy
            * hidden.network_quality      # network must be good
            * hidden.customer_liquidity   # customer must have funds
        )
        # Retry fatigue: each additional retry reduces probability
        fatigue = max(0.0, 1.0 - customer_retry_count * 0.25)
        prob *= fatigue
        return float(np.clip(prob, 0.0, 1.0))

    def outcome_if_retry_later(
        self,
        hidden: HiddenFactors,
        customer_retry_count: int = 0,
    ) -> float:
        """
        P(success | retry_after_delay, hidden_factors).

        Waiting gives transient issues (issuer overload, network blip) time
        to resolve. Customer/system state may improve. Less fatigue.
        """
        base = 0.90  # higher base — time helps
        prob = (
            base
            * hidden.issuer_health
            * hidden.customer_liquidity
            * hidden.customer_intent
        )
        # Less fatigue than immediate retry
        fatigue = max(0.0, 1.0 - customer_retry_count * 0.10)
        prob *= fatigue
        return float(np.clip(prob, 0.0, 1.0))

    def outcome_if_payment_link(self, hidden: HiddenFactors) -> float:
        """
        P(success | send_payment_link, hidden_factors).

        Payment link requires active customer action — success depends on:
        - Customer intent (will they click?)
        - Customer persistence (will they complete?)
        - Customer liquidity (can they pay?)

        Less dependent on issuer/network health (fresh attempt, different window).
        """
        base = 0.88
        prob = (
            base
            * hidden.customer_intent
            * hidden.payment_persistence
            * hidden.customer_liquidity
        )
        return float(np.clip(prob, 0.0, 1.0))

    def generate_observable_features(
        self, hidden: HiddenFactors
    ) -> dict[str, float | int | str]:
        """
        Map hidden causal factors → observable features.

        These are what the ML model actually sees. They are noisy proxies
        for the hidden factors — correlated but not identical.

        Noise is intentional: it represents measurement imprecision,
        feature staleness, and model uncertainty.
        """
        # Payment amount: log-normal (right-skewed, realistic for India)
        amount = float(self.rng.lognormal(10.5, 1.5))  # paise, ~₹36k median

        # Payment method: card=0, upi=1, netbanking=2, wallet=3
        payment_method = int(self.rng.choice(4, p=[0.35, 0.40, 0.15, 0.10]))

        # Bank (6 major issuers)
        bank = int(self.rng.choice(6))

        # Latency: reflects network quality + system load (with noise)
        base_latency = 200 + (1 - hidden.network_quality) * 2500
        latency = float(max(50, base_latency + self.rng.normal(0, 100)))

        # Error code: reflects issuer health
        if hidden.issuer_health < 0.3:
            error_code = "ISSUER_TIMEOUT"
        elif hidden.issuer_health < 0.6:
            error_code = "AUTHORIZATION_FAILED"
        else:
            error_code = "SUCCESS"

        # Customer history features (derived from intent + persistence)
        customer_days_active = int(
            max(1, 100 * hidden.customer_intent + self.rng.normal(0, 20))
        )
        customer_success_rate = float(
            np.clip(hidden.customer_intent * 0.9 + 0.05 + self.rng.normal(0, 0.05), 0, 1)
        )
        customer_churn_risk = float(
            np.clip(1 - hidden.payment_persistence + self.rng.normal(0, 0.1), 0, 1)
        )

        return {
            "amount": amount,
            "payment_method": payment_method,
            "bank": bank,
            "latency_ms": latency,
            "error_code": error_code,
            "customer_days_active": customer_days_active,
            "customer_success_rate": customer_success_rate,
            "customer_churn_risk": customer_churn_risk,
        }
