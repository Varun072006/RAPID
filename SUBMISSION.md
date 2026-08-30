# Razorpay AI Buildathon 2026 — RAPID Submission

## Track

**Track 03 — AI Revenue Recovery**

## Links

- **GitHub**: https://github.com/Varun072006/rapid-payment-recovery
- **Pitch Video**: [YouTube link — add before submission]
- **Live Demo**: `docker-compose up` → http://localhost:3000

---

## One-Sentence Pitch

RAPID is a production-inspired payment recovery engine that reconstructs true payment state from asynchronous webhooks, predicts recovery outcomes for alternative actions using calibrated ML models, optimizes for expected net revenue, enforces deterministic policy gates, executes Test Mode workflows, reconciles timeouts safely, and delivers measurable revenue recovery with zero policy violations and zero double-charge risk.

---

## Core Differentiator

**Unknown-state reconciliation**: When an API call times out, RAPID does not retry blindly. It marks the payment as `UNKNOWN`, queries Razorpay's authoritative state, and only proceeds if safe.

```
Timeout occurs
      ↓
State = UNKNOWN (not FAILED)
      ↓
Policy Engine: DENY all retries
      ↓
Reconciler: GET /payments/{id} from Razorpay
      ↓
True state: CAPTURED → no action (already succeeded)
True state: FAILED   → safe to recover
True state: PENDING  → wait, do not retry
True state: UNKNOWN  → escalate to human
```

This eliminates 100% of double-charge risk from timeouts (145 → 0 unknown-state errors vs baseline).

---

## Results

| Metric               | Baseline (Fixed Retry) | Rule-Based | RAPID    |
| -------------------- | ---------------------- | ---------- | -------- |
| Recovery Rate        | ~62%                   | ~68%       | **~72%** |
| Unnecessary Retries  | ~8%                    | ~4%        | **~2%**  |
| Unknown-State Errors | 145                    | 98         | **0**    |
| Policy Violations    | 0                      | 0          | **0**    |

**Distribution shift test**: At 1.5× bank failure rate increase, RAPID accuracy degraded < 3% (graceful).

---

## Tech Stack

| Layer         | Technology                         |
| ------------- | ---------------------------------- |
| Runtime       | Python 3.12 + uv                   |
| API           | FastAPI + Pydantic v2              |
| Database      | PostgreSQL 16 + SQLAlchemy 2       |
| ML            | scikit-learn (GBM + calibrated LR) |
| LLM           | Qwen3 8B/14B via Ollama (local)    |
| Frontend      | Next.js 15 + TypeScript + Tailwind |
| Testing       | pytest + Hypothesis                |
| Observability | Prometheus + OpenTelemetry         |
| Deployment    | Docker Compose                     |

---

## Evaluation Methodology

1. **100K synthetic scenarios** with causal structure (hidden factors → observable features → outcomes)
2. **Train/val/test/shift split** (60/20/10/10)
3. **Three baselines**: fixed 6h retry, rule-based, RAPID
4. **Business metrics**: recovery rate, amount recovered, unnecessary retries, policy violations
5. **Distribution-shift test**: 1.5× bank failure rate + elevated latency
6. **Calibration**: Brier score + ECE for all 3 recovery models

---

## Key Files

| File                                                 | Purpose                      |
| ---------------------------------------------------- | ---------------------------- |
| `apps/api/main.py`                                   | FastAPI entry point          |
| `packages/domain/payments/state_machine.py`          | Payment state transitions    |
| `packages/domain/payments/models.py`                 | ORM models                   |
| `packages/integrations/razorpay/adapter.py`          | Razorpay API (real)          |
| `packages/integrations/razorpay/mock_adapter.py`     | Simulator (no credentials)   |
| `packages/ml/simulation/causal_model.py`             | Causal world model           |
| `packages/domain/recovery/optimizer.py`              | Expected net value optimizer |
| `packages/domain/policy/engine.py`                   | 5-rule policy gate           |
| `packages/workflows/reconciliation/unknown_state.py` | Timeout reconciler           |
| `packages/workflows/recovery/orchestrator.py`        | End-to-end pipeline          |
| `packages/workflows/recovery/agent.py`               | Ollama/Qwen3 agent           |

---

## Security

- ✅ Razorpay keys in `.env` (never in git)
- ✅ Webhook HMAC verified over **raw body** (not parsed JSON)
- ✅ Idempotency keys on all mutating Razorpay calls
- ✅ No LLM access to payment credentials
- ✅ Input validation via Pydantic on all endpoints
- ✅ SQLAlchemy parameterized queries (no raw SQL)
- ✅ Deduplication via DB unique constraint (no distributed lock)

---

## How to Run

```bash
# No Razorpay keys needed — runs in mock mode by default
git clone https://github.com/Varun072006/rapid-payment-recovery.git
cd rapid-payment-recovery
cp .env.example .env

# Install uv (if not present)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows
# or: curl -LsSf https://astral.sh/uv/install.sh | sh        # macOS/Linux

# Install dependencies
uv sync --all-extras

# Start services
docker-compose up -d

# Generate data + train models
make data && make train && make evaluate

# Run demo
python scripts/demo.py

# Open dashboard
# http://localhost:3000
```

---

## Known Limitations

1. **Circular synthetic evaluation**: Train/test on data from same simulator. Real validation requires production data.
2. **Sparse merchant histories**: Model performs worse on new merchants.
3. **Fixed global policy**: Real system would have per-merchant policies.
4. **No drift detection**: Requires monitoring + periodic retraining.

---

## What We Did NOT Build (Intentionally)

- Fraud detection
- Chargeback prediction
- KYC flows
- Kafka at scale
- Kubernetes
- Voice recovery agent

We owned **one problem deeply** — payment recovery with correctness guarantees.

---

## Open-Source Commitment

Licensed MIT. Open-sourced immediately after buildathon concludes.

---

**Author**: Varun S (@Varun072006)
