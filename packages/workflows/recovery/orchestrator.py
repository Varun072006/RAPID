"""
Recovery orchestrator — end-to-end pipeline for failed payment recovery.

Pipeline:
    1. Load payment from DB
    2. Extract ML features
    3. Classify failure mode
    4. Predict P(recovery) per action
    5. Revenue optimizer: select best action by expected net value
    6. Agent: synthesize decision + explanation
    7. Policy engine: authorize or deny
    8. Idempotency key generation
    9. Execute via Razorpay adapter
   10. Write audit events at every step
   11. Return structured result
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from packages.domain.payments.models import Payment, PaymentState, RecoveryDecision, RecoveryAction
from packages.domain.recovery.optimizer import RevenueOptimizer
from packages.domain.recovery.system_health import HealthDetector
from packages.domain.policy.engine import PolicyEngine
from packages.integrations.razorpay.adapter import RazorpayAdapter
from packages.ml.features.engineering import ERROR_CODE_MAP, FEATURE_COLUMNS, extract_features
from packages.utils.audit import AuditLogger
from packages.utils.idempotency import IdempotencyKeyGenerator
from packages.workflows.recovery.agent import RecoveryAgent

MODEL_DIR = Path("packages/ml/models")


def _load_models() -> tuple[Any, Any]:
    """Load ML models from disk (lazy-loaded once at startup)."""
    failure_path = MODEL_DIR / "failure_classifier.pkl"
    recovery_path = MODEL_DIR / "recovery_models.pkl"

    if not failure_path.exists() or not recovery_path.exists():
        raise FileNotFoundError(
            "ML models not found. Run: make data && make train"
        )

    with open(failure_path, "rb") as f:
        failure_clf = pickle.load(f)
    with open(recovery_path, "rb") as f:
        recovery_bundle = pickle.load(f)

    return failure_clf, recovery_bundle


class RecoveryOrchestrator:
    """
    Coordinates the full recovery pipeline for a single failed payment.

    One instance per application, shared across requests.
    """

    def __init__(
        self,
        razorpay: RazorpayAdapter,
        optimizer: RevenueOptimizer,
        policy: PolicyEngine,
        health_detector: HealthDetector,
        agent: RecoveryAgent,
        db: Session,
    ) -> None:
        self.razorpay = razorpay
        self.optimizer = optimizer
        self.policy = policy
        self.health_detector = health_detector
        self.agent = agent
        self.db = db
        self.audit = AuditLogger(db)

        # Lazy-loaded ML models
        self._failure_clf = None
        self._recovery_bundle = None

    def _ensure_models(self) -> None:
        if self._failure_clf is None:
            self._failure_clf, self._recovery_bundle = _load_models()
            logger.info("ML models loaded")

    def _predict_failure_mode(self, features_dict: dict) -> tuple[str, float]:
        """Classify the failure mode and return (mode, confidence)."""
        feature_vec = [[features_dict[col] for col in FEATURE_COLUMNS]]
        mode = self._failure_clf.predict(feature_vec)[0]
        proba = max(self._failure_clf.predict_proba(feature_vec)[0])
        return mode, float(proba)

    def _predict_recovery_probs(
        self, features_dict: dict
    ) -> dict[str, float]:
        """Predict P(success) for each recovery action."""
        scaler = self._recovery_bundle["scaler"]
        models = self._recovery_bundle["models"]

        feature_vec = [[features_dict[col] for col in FEATURE_COLUMNS]]
        scaled = scaler.transform(feature_vec)

        return {
            action: float(model.predict_proba(scaled)[0][1])
            for action, model in models.items()
        }

    def process_failed_payment(self, payment_id: str) -> dict:
        """
        Run the full recovery pipeline for one failed payment.

        Returns a structured result dict describing every step taken.
        """
        self._ensure_models()

        # ── Step 1: Load payment ──────────────────────────────────────────
        payment = (
            self.db.query(Payment)
            .filter(Payment.payment_id == payment_id)
            .first()
        )

        if not payment:
            return {"error": f"Payment {payment_id} not found", "success": False}

        if payment.state not in (PaymentState.FAILED, PaymentState.UNKNOWN):
            return {
                "error": f"Payment {payment_id} is in state {payment.state.value}, "
                         f"expected FAILED or UNKNOWN",
                "success": False,
            }

        logger.info(
            f"Processing recovery: {payment_id} "
            f"amount=₹{payment.amount/100:.2f} "
            f"state={payment.state.value}"
        )

        # ── Step 2: Extract features ──────────────────────────────────────
        payment_dict = {
            "amount": payment.amount,
            "payment_method": payment.payment_method or "card",
            "bank": payment.bank or "0",
            "latency_ms": 500,            # default; real system reads from logs
            "error_code": "AUTHORIZATION_FAILED",
            "customer_days_active": 30,
            "customer_success_rate": 0.7,
            "customer_churn_risk": 0.3,
        }
        # Encode error_code
        payment_dict["error_code"] = ERROR_CODE_MAP.get(
            str(payment_dict["error_code"]), 1
        )
        # Encode payment_method
        from packages.ml.features.engineering import PAYMENT_METHOD_MAP
        payment_dict["payment_method"] = PAYMENT_METHOD_MAP.get(
            str(payment_dict["payment_method"]), 0
        )
        try:
            payment_dict["bank"] = int(payment_dict["bank"])
        except (ValueError, TypeError):
            payment_dict["bank"] = 0

        # ── Step 3: Classify failure mode ─────────────────────────────────
        failure_mode, failure_confidence = self._predict_failure_mode(payment_dict)
        self.audit.failure_classified(payment_id, failure_mode, failure_confidence)
        logger.info(
            f"Failure classified: {failure_mode} ({failure_confidence:.0%} confidence)"
        )

        # ── Step 4: Predict recovery probabilities ────────────────────────
        recovery_probs = self._predict_recovery_probs(payment_dict)
        self.audit.recovery_predicted(payment_id, recovery_probs)
        logger.info(f"Recovery predictions: {recovery_probs}")

        # ── Step 5: Revenue optimizer ─────────────────────────────────────
        best_action, all_evals = self.optimizer.select_best_action(
            recovery_probs, payment.amount
        )
        best_eval = next(e for e in all_evals if e.action == best_action)
        self.audit.action_selected(
            payment_id,
            best_action,
            best_eval.expected_net_value,
            [
                {
                    "action": e.action,
                    "recovery_prob": e.recovery_prob,
                    "expected_net_value": e.expected_net_value,
                }
                for e in all_evals
            ],
        )

        # ── Step 6: Agent synthesis ───────────────────────────────────────
        payment_context = {
            "payment_id": payment_id,
            "amount_inr": payment.amount / 100,
            "payment_method": payment.payment_method,
            "state": payment.state.value,
            "failure_mode": failure_mode,
            "retry_count": payment.retry_count,
        }
        agent_proposal = self.agent.propose_recovery(
            payment_context, recovery_probs
        )

        # ── Step 7: Policy check ──────────────────────────────────────────
        system_healthy = not self.health_detector.should_pause_retries()
        authorized, policy_reason = self.policy.authorize_action(
            action=best_action,
            amount=payment.amount,
            recovery_confidence=best_eval.recovery_prob,
            current_state=payment.state.value,
            retry_count=payment.retry_count,
            system_healthy=system_healthy,
        )
        self.audit.policy_checked(payment_id, best_action, authorized, policy_reason)

        if not authorized:
            # Record denied decision
            decision = RecoveryDecision(
                payment_id=payment_id,
                action=RecoveryAction[best_action.upper().replace("-", "_")],
                predicted_probability=best_eval.recovery_prob,
                expected_value=best_eval.expected_net_value,
                policy_authorized=False,
                policy_reason=policy_reason,
                executed=False,
                agent_diagnosis=agent_proposal.get("diagnosis", ""),
                agent_reason=agent_proposal.get("reason", ""),
            )
            self.db.add(decision)
            self.db.commit()

            return {
                "payment_id": payment_id,
                "success": False,
                "authorized": False,
                "action": best_action,
                "policy_reason": policy_reason,
                "agent_proposal": agent_proposal,
                "predictions": recovery_probs,
            }

        # ── Step 8: Idempotency key ───────────────────────────────────────
        idempotency_key = IdempotencyKeyGenerator.generate(
            payment_id=payment_id,
            action_type=best_action,
            merchant_id=payment.merchant_id,
        )

        # ── Step 9: Execute ───────────────────────────────────────────────
        execution_result: dict = {}
        executed = False

        try:
            if best_action == "payment_link":
                result = self.razorpay.create_payment_link(
                    amount=payment.amount,
                    customer_id=payment.customer_id,
                    description=f"Payment recovery for {payment_id}",
                    idempotency_key=idempotency_key,
                )
                execution_result = result
                executed = True
                payment.state = PaymentState.PAYMENT_LINK_SENT

            elif best_action in ("retry_now", "retry_later"):
                # Retry requires re-authorization via new payment — escalate for now
                # (Full retry flow requires creating a new Razorpay order)
                payment.state = PaymentState.ESCALATED
                execution_result = {
                    "note": f"{best_action} queued — retry flow requires new order creation",
                    "next": "escalated_for_retry",
                }
                executed = True

            payment.retry_count += 1
            self.db.commit()

            self.audit.action_executed(
                payment_id, best_action, idempotency_key, execution_result
            )

        except Exception as exc:
            logger.error(f"Execution failed for {payment_id}: {exc}")
            execution_result = {"error": str(exc)}

        # Record decision
        action_enum_name = best_action.upper().replace("-", "_")
        try:
            action_enum = RecoveryAction[action_enum_name]
        except KeyError:
            action_enum = RecoveryAction.DO_NOTHING

        decision = RecoveryDecision(
            payment_id=payment_id,
            action=action_enum,
            predicted_probability=best_eval.recovery_prob,
            expected_value=best_eval.expected_net_value,
            policy_authorized=authorized,
            policy_reason=policy_reason,
            executed=executed,
            execution_result=str(execution_result.get("id", execution_result)),
            idempotency_key=idempotency_key,
            agent_diagnosis=agent_proposal.get("diagnosis", ""),
            agent_reason=agent_proposal.get("reason", ""),
        )
        self.db.add(decision)
        self.db.commit()

        logger.info(
            f"Recovery complete: {payment_id} → {best_action} "
            f"executed={executed}"
        )

        return {
            "payment_id": payment_id,
            "success": executed,
            "authorized": True,
            "action": best_action,
            "policy_reason": policy_reason,
            "predictions": recovery_probs,
            "expected_value_inr": best_eval.expected_net_value / 100,
            "execution_result": execution_result,
            "agent_proposal": agent_proposal,
            "idempotency_key": idempotency_key,
        }
