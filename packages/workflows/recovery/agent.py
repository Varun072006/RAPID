"""
Recovery agent — LLM-powered decision proposal using Ollama + Qwen3.

Architecture:
    ML models predict probabilities.
    Revenue optimizer selects best action by expected value.
    THIS agent explains the decision in human-readable terms
    and can override the optimizer's choice with structured reasoning.

LLM: Qwen3 8B or 14B via Ollama (local, no API key needed).
Fallback: deterministic logic if Ollama is unavailable.

To set up Ollama:
    1. Install from https://ollama.com
    2. Run: ollama pull qwen3:8b
    3. Ensure OLLAMA_HOST=http://localhost:11434 in .env
    4. Set LLM_PROVIDER=ollama in .env

To run without LLM:
    Set LLM_PROVIDER=mock in .env
    → Returns deterministic proposals based on ML predictions only
"""

from __future__ import annotations

import json
import os
from typing import Any

from loguru import logger


class RecoveryAgent:
    """
    LLM-based structured decision proposal.

    Input:  payment context + ML predictions + policy constraints
    Output: structured JSON proposal
        {
            "diagnosis": str,
            "recommended_action": str,
            "reason": str,
            "confidence": float,
            "reasoning_notes": str  (Qwen3 thinking trace, if available)
        }

    The agent PROPOSES. The policy engine AUTHORIZES. No exceptions.
    """

    SYSTEM_PROMPT = """You are RAPID's recovery decision agent for a payment processing system.
Your job is to analyze a failed payment and recommend the best recovery action.

Available actions:
- retry_now: Immediately retry the payment
- retry_later: Schedule retry after a delay (usually 30-60 min)
- payment_link: Send the customer a fresh payment link
- escalate: Route to human review

You must respond ONLY with valid JSON (no markdown, no extra text):
{
  "diagnosis": "One sentence describing the failure cause",
  "recommended_action": "retry_now|retry_later|payment_link|escalate",
  "reason": "Why this action is best given the context",
  "confidence": 0.0
}"""

    def __init__(
        self,
        model: str | None = None,
        ollama_host: str | None = None,
        provider: str | None = None,
    ) -> None:
        self.model = model or os.getenv("LLM_MODEL", "qwen3:8b")
        self.ollama_host = ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.provider = provider or os.getenv("LLM_PROVIDER", "mock")

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama REST API and return raw response text."""
        try:
            import httpx

            response = httpx.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent JSON
                        "num_predict": 512,
                    },
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as exc:
            logger.warning(f"Ollama call failed: {exc} — falling back to mock")
            return ""

    def _deterministic_proposal(
        self,
        payment_context: dict[str, Any],
        predictions: dict[str, float],
    ) -> dict:
        """
        Fallback: deterministic proposal when LLM is unavailable.
        Selects action with highest predicted probability.
        """
        best_action = max(predictions, key=lambda k: predictions[k])
        best_prob = predictions[best_action]

        failure_mode = payment_context.get("failure_mode", "unknown")
        diagnosis_map = {
            "transient": "Transient issuer or network failure — likely to resolve quickly",
            "customer_action_needed": "Customer must take action to complete payment",
            "infrastructure": "System-wide degradation detected — retry after delay",
            "customer_issue": "Structural customer issue — funds, fraud, or abandonment",
            "unknown": "Failure cause undetermined — defaulting to highest probability action",
        }

        return {
            "diagnosis": diagnosis_map.get(failure_mode, diagnosis_map["unknown"]),
            "recommended_action": best_action,
            "reason": (
                f"ML model predicts {best_prob:.0%} success probability "
                f"for {best_action} (highest among all actions). "
                f"Failure classified as: {failure_mode}."
            ),
            "confidence": best_prob,
            "reasoning_notes": "Deterministic fallback (LLM unavailable)",
        }

    def propose_recovery(
        self,
        payment_context: dict[str, Any],
        predictions: dict[str, float],
        policy_check: dict[str, Any] | None = None,
    ) -> dict:
        """
        Propose a recovery action using LLM reasoning.

        Args:
            payment_context: Payment details (amount, method, state, failure_mode)
            predictions:     ML model predictions {action: probability}
            policy_check:    Policy constraints to inform the LLM

        Returns:
            Structured proposal dict.
        """
        if self.provider == "mock":
            return self._deterministic_proposal(payment_context, predictions)

        # Build prompt
        prompt = f"""Payment recovery analysis request:

Payment context:
{json.dumps(payment_context, indent=2, default=str)}

ML model predictions (P(success) per action):
{json.dumps(predictions, indent=2)}

Policy constraints:
{json.dumps(policy_check or {}, indent=2)}

Based on this information, provide a recovery recommendation."""

        full_prompt = f"{self.SYSTEM_PROMPT}\n\n{prompt}"

        logger.debug(f"Calling {self.model} via Ollama for payment proposal...")
        raw = self._call_ollama(full_prompt)

        if not raw:
            logger.warning("Empty LLM response — using deterministic fallback")
            return self._deterministic_proposal(payment_context, predictions)

        # Parse JSON response
        try:
            # Strip markdown fences if present
            clean = raw.strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                clean = "\n".join(lines[1:-1])

            proposal = json.loads(clean)

            # Validate required fields
            required = {"diagnosis", "recommended_action", "reason", "confidence"}
            if not required.issubset(proposal.keys()):
                raise ValueError(f"Missing fields: {required - proposal.keys()}")

            proposal["reasoning_notes"] = f"Qwen3 via Ollama ({self.model})"
            logger.info(
                f"LLM proposal: action={proposal['recommended_action']} "
                f"confidence={proposal['confidence']:.0%}"
            )
            return proposal

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                f"Failed to parse LLM response ({exc}) — using deterministic fallback. "
                f"Raw: {raw[:200]}"
            )
            return self._deterministic_proposal(payment_context, predictions)
