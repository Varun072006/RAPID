# Architecture — RAPID Payment Recovery Engine

## Overview

RAPID is a bounded-autonomy system for payment recovery. It processes asynchronous Razorpay events, reconstructs authoritative payment state, and autonomously recovers failed payments within policy bounds.

## Component Diagram

```
┌──────────────────────────────────────────────────────────┐
│                    Razorpay / Mock                       │
│                  (Webhooks + REST API)                   │
└─────────────────────────┬────────────────────────────────┘
                          │ HTTPS + HMAC-SHA256
                          ▼
┌──────────────────────────────────────────────────────────┐
│               FastAPI (apps/api/)                        │
│  /webhooks/razorpay   /api/payments   /api/recovery      │
│  /api/metrics         /api/demo       /metrics (Prom)    │
└───────┬────────────────────┬─────────────────────────────┘
        │                    │
        ▼                    ▼
┌───────────────┐   ┌─────────────────────────────────────┐
│  Deduplicator │   │     Recovery Orchestrator           │
│  (event_id)   │   │                                     │
└───────┬───────┘   │  1. Failure Classifier (GBM)        │
        │           │  2. Recovery Predictors × 3 (LR)   │
        ▼           │  3. Revenue Optimizer (ENv)         │
┌───────────────┐   │  4. Agent (Qwen3 / mock)            │
│  Event Store  │   │  5. Policy Engine (5 rules)         │
│  (audit log)  │   │  6. Idempotency + Execution         │
└───────┬───────┘   └──────────────┬──────────────────────┘
        │                          │
        ▼                          ▼
┌───────────────┐   ┌─────────────────────────────────────┐
│ State Machine │   │         Razorpay Adapter            │
│  (transitions)│   │  (Real Test Mode or Mock)           │
└───────────────┘   └─────────────────────────────────────┘
        │
        ▼
┌───────────────┐
│  PostgreSQL   │  payments, recovery_decisions,
│               │  audit_events, webhook_received_events
└───────────────┘
```

## Data Flow

### Webhook Path
1. Razorpay sends `POST /webhooks/razorpay`
2. FastAPI reads **raw body** (required for HMAC verification)
3. HMAC-SHA256 signature verified against webhook secret
4. `event_id` extracted from header
5. Deduplicator checks `webhook_received_events` table
6. If duplicate → return 200 "deduplicated" (never 4xx — causes Razorpay to retry)
7. If new → mark processed (atomic, DB constraint)
8. Map Razorpay event type → internal `PaymentState`
9. `EventSequencer.process_event()` validates via `StateMachine`
10. If valid → update `Payment.state` + commit
11. `EventStore.append_event()` records audit entry

### Recovery Path
1. `POST /api/recovery/process?payment_id=pay_xxx`
2. Load `Payment` from DB
3. Extract features → encode for sklearn
4. `FailureClassifier.predict()` → failure mode + confidence
5. `RecoveryModels.predict_proba()` → P(success) per action
6. `RevenueOptimizer.select_best_action()` → best action by ENv
7. `RecoveryAgent.propose_recovery()` → LLM diagnosis + reason
8. `PolicyEngine.authorize_action()` → authorized or denied
9. If authorized → `IdempotencyKeyGenerator.generate()`
10. `RazorpayAdapter.create_payment_link()` (or mock)
11. Update payment state, increment retry_count
12. `AuditLogger` records every step

### Timeout Reconciliation Path
1. Action times out → payment state = `UNKNOWN`
2. `PolicyEngine` denies all retry actions (Rule 1)
3. `UnknownStateResolver.apply_reconciliation()` called
4. `RazorpayAdapter.fetch_payment()` queries authoritative state
5. Map status → `ReconciliationOutcome`
6. Update payment state accordingly
7. Return `safe_to_retry` flag to caller

## Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| API | FastAPI | Type-safe, OpenAPI, async |
| DB | PostgreSQL 16 | ACID, constraints for dedup |
| ML | scikit-learn + XGBoost | CPU-only, interpretable |
| LLM | Ollama + Qwen3 | Local, no API key, private |
| Frontend | Next.js 15 | Fast, TypeScript-native |
| Packaging | uv | 10–100× faster than pip |

## Scalability Notes

Current architecture is single-instance (prototype). Production would require:
- Redis-backed sliding window for `HealthDetector`
- Kafka instead of Redis Streams for event processing at scale
- Horizontal FastAPI replicas behind a load balancer
- Connection pooling (PgBouncer)
- ML model serving via dedicated inference service
