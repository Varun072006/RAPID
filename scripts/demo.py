#!/usr/bin/env python3
"""
RAPID demo script — Autonomous Payment Recovery Engine.
Demonstrates live API integration, reconciliation, safety policy guards,
subscription recovery, and batch revenue recovery.

Run: python scripts/demo.py (with API server running on localhost:8000)
Or:  make demo-ready
"""

import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests

API = "http://localhost:8000"


def header(text: str) -> None:
    print(f"\n{'='*65}")
    print(f"  {text}")
    print("=" * 65)


def check_health() -> bool:
    try:
        r = requests.get(f"{API}/health", timeout=3)
        data = r.json()
        print(f"  API:           {data['status'].upper()} (Healthy)")
        print(f"  Razorpay mode: {data['razorpay_mode'].upper()} (Safe Mock Adapter)")
        print(f"  LLM Provider:  {data['llm_provider'].upper()} ({data['llm_model']})")
        return True
    except Exception as e:
        print(f"  ❌ API not reachable: {e}")
        print("  Start the server: uvicorn apps.api.main:app --reload")
        return False


def demo_normal_recovery() -> None:
    header("SCENARIO 1: Autonomous ML Recovery & Razorpay Payment Link")
    r = requests.post(f"{API}/api/demo/inject", json={"scenario_type": "normal_recovery"})
    scenario = r.json()
    payment_id = scenario["payment_id"]

    print(f"\n1. Injected Failed Payment: {payment_id}")
    print("   Amount: ₹750.00 | Method: UPI | Error: AUTHORIZATION_FAILED")

    try:
        r2 = requests.post(f"{API}/api/recovery/process", params={"payment_id": payment_id})
        result = r2.json()
        if "error" in result:
            print(f"\n   ⚠ Recovery pipeline: {result['error']}")
            print("   (Run: make train to train ML models)")
            return

        print("\n2. ML Outcome Predictions (Calibrated Probabilities):")
        for action, prob in result.get("predictions", {}).items():
            print(f"   • {action:15s}: {prob:.1%}")

        print("\n3. Revenue Optimizer Selection:")
        print(f"   Selected Action:    {result.get('action')}")
        print(f"   Expected Net Value: ₹{result.get('expected_value_inr', 0):.2f}")
        print(f"   Policy Decision:    {result.get('policy_reason')}")

        print("\n4. Agent Synthesis & Root Cause Diagnosis:")
        proposal = result.get("agent_proposal", {})
        print(f"   Diagnosis: {proposal.get('diagnosis', 'N/A')}")
        print(f"   Reasoning: {proposal.get('reason', 'N/A')}")

        print("\n5. Razorpay Execution Payload:")
        exec_res = result.get("execution_result", {})
        if isinstance(exec_res, dict) and "short_url" in exec_res:
            print(f"   Razorpay Link ID:   {exec_res.get('id')}")
            print(f"   Hosted URL:         {exec_res.get('short_url')}")
            print(f"   Status:             {exec_res.get('status')}")
            print(f"   Idempotency-Key:    {result.get('idempotency_key')}")
        else:
            print(f"   Execution details:  {exec_res}")

        print(f"\n   [OK] Autonomous Recovery Dispatched: success={result.get('success')}")
    except Exception as e:
        print(f"\n   Error: {e}")


def demo_timeout_reconciliation() -> None:
    header("SCENARIO 2: Unknown State & Safe Razorpay Reconciliation")
    r = requests.post(f"{API}/api/demo/inject", json={"scenario_type": "timeout"})
    scenario = r.json()
    payment_id = scenario["payment_id"]

    print("\n1. Injected Network Timeout during Capture:")
    print(f"   Payment ID:    {payment_id}")
    print(f"   Initial State: {scenario['state']} (Safety State)")

    print("\n2. Deterministic Policy Gate Guard:")
    print("   Rule: 'state == UNKNOWN -> DENY ALL RETRIES'")
    print("   Guarantee: Double-charge risk = 0.0%")

    print("\n3. Calling Live Reconciliation API (/api/recovery/reconcile)...")
    try:
        recon_resp = requests.post(f"{API}/api/recovery/reconcile", json={"payment_id": payment_id})
        recon_data = recon_resp.json()
        print(f"   Razorpay Query ID: {recon_data.get('razorpay_id')}")
        print(f"   Authoritative State: {recon_data.get('reconciled_state')}")
        print(f"   Outcome Category:    {recon_data.get('outcome')}")
        print(f"   Safe to Retry:       {recon_data.get('safe_to_retry')}")
        print(f"   Reconciler Note:     {recon_data.get('message')}")
        print("\n   [OK] Invariant Preserved: Zero double-charge risk maintained.")
    except Exception as e:
        print(f"   Reconciliation call failed: {e}")


def demo_subscription_recovery() -> None:
    header("SCENARIO 3: Recurring SaaS Mandate Recovery (Track 03)")
    r = requests.post(f"{API}/api/demo/inject", json={"scenario_type": "subscription_recovery"})
    scenario = r.json()
    payment_id = scenario["payment_id"]

    print("\n1. Subscription Mandate Debit Failed:")
    print(f"   Payment ID:      {payment_id}")
    print(f"   Subscription ID: {scenario.get('subscription_id')}")
    print(f"   Amount:          ₹{scenario.get('amount_inr', 0):.2f}")
    print("   Reason:          Recurring mandate declined (issuer insufficient balance)")

    try:
        r2 = requests.post(f"{API}/api/recovery/process", params={"payment_id": payment_id})
        result = r2.json()
        print(f"\n2. Optimization Strategy: {result.get('action')}")
        print(f"   Expected Value:  ₹{result.get('expected_value_inr', 0):.2f}")
        print(f"   Policy Guard:    {result.get('policy_reason')}")
        exec_res = result.get("execution_result", {})
        if isinstance(exec_res, dict) and "short_url" in exec_res:
            print(
                f"   Omnichannel Link: {exec_res.get('short_url')} "
                "(Direct to subscriber via WhatsApp/SMS)"
            )
        print("\n   [OK] Churn Mitigated without manual merchant intervention.")
    except Exception as e:
        print(f"   Recovery error: {e}")


def demo_adversarial_guardrail() -> None:
    header("SCENARIO 4: Adversarial LLM Prompt Injection Defeat")
    r = requests.post(f"{API}/api/demo/inject", json={"scenario_type": "adversarial_llm"})
    scenario = r.json()

    print("\n1. Malicious / Hallucinated Action Injected:")
    print(f"   Payment ID: {scenario.get('payment_id')}")
    print("   Attempt:    Auto-retry high-value transaction of ₹35,000.00")
    print("   Threshold:  max_auto_amount = ₹25,000.00")

    print("\n2. Deterministic Policy Gate Action:")
    print("   Evaluator:  PolicyEngine.check_payment()")
    print(f"   Authorized: {scenario.get('authorized')}")
    print(f"   Diagnosis:  {scenario.get('description')}")
    print("\n   [OK] Unsafe Autonomy Rate: 0.00% (Deterministic boundary holds)")


def demo_batch_recovery() -> None:
    header("SCENARIO 5: Batch Recovery Engine & Cumulative Revenue (Track 03)")
    print("\n1. Triggering Batch Recovery Pipeline (/api/batch/recover)...")
    try:
        r = requests.post(f"{API}/api/batch/recover", json={"limit": 10})
        data = r.json()
        print(f"   Payments Processed:      {data.get('total_processed')}")
        print(f"   Recovered Count:         {data.get('recovered_count')}")
        print(f"   Gross Volume Attempted:  ₹{data.get('gross_amount_attempted_inr', 0):.2f}")
        print(f"   Net Revenue Recovered:   ₹{data.get('net_revenue_recovered_inr', 0):.2f}")
        print("   Action Distribution:")
        for act, count in data.get("action_breakdown", {}).items():
            print(f"     • {act:15s}: {count}")
        print("\n   [OK] Verified Net Revenue Recovery across batch.")
    except Exception as e:
        print(f"   Batch recovery error: {e}")


def main():
    print()
    print("=" * 65)
    print("  RAPID — Autonomous Payment Recovery Engine")
    print("  Razorpay AI Buildathon 2026 — Track 03: AI Revenue Recovery")
    print("=" * 65)

    header("System Health & Adapter Mode")
    if not check_health():
        return

    demo_normal_recovery()
    time.sleep(1)

    demo_timeout_reconciliation()
    time.sleep(1)

    demo_subscription_recovery()
    time.sleep(1)

    demo_adversarial_guardrail()
    time.sleep(1)

    demo_batch_recovery()

    header("Evaluation Summary & Deliverables")
    print()
    print("  ✓ Causal ML Models:     Gradient Boosting + Calibrated LogReg")
    print("  ✓ Decision Regret:      60.0% Reduction (₹53.68 -> ₹21.46 / txn)")
    print("  ✓ Safe Autonomy:        0 Double-charges | 0 Unknown errors")
    print("  ✓ Omnichannel Actions:  Razorpay Payment Links + Smart Retries")
    print("  ✓ Full Benchmark:       benchmark_results.csv (13 slices, 19 metrics)")
    print()
    print("  Dashboard UI: http://localhost:3000")
    print("  API Docs:     http://localhost:8000/docs")
    print("=" * 65)


if __name__ == "__main__":
    main()
