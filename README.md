# RAPID

**Revenue-optimized Autonomous Payment Intervention & Decision Engine**  
Razorpay AI Buildathon 2026 | Track 03: AI Revenue Recovery

RAPID is a correctness-focused payment recovery engine. It reconstructs payment state from asynchronous Razorpay webhooks, predicts recovery outcomes, selects actions by expected net value, and applies deterministic safety policy before any financial side effect.

> **AI recommends. Policy authorizes. The state machine protects payment semantics.**

## Why RAPID

Naive retries can duplicate charges after timeouts, amplify bank incidents, and waste money on actions that have poor net value. RAPID treats recovery as a bounded-autonomy workflow:

1. Verify the raw webhook cryptographically.
2. Deduplicate and sequence provider events.
3. Reconstruct the authoritative local payment state.
4. Reconcile `UNKNOWN` payments before any retry.
5. Predict failure mode and action-specific recovery probability.
6. Optimize expected net value, including cost, friction, and risk.
7. Apply deterministic policy gates.
8. Execute through a Razorpay adapter with idempotency.
9. Record the complete audit trail.

## Core Capabilities

- HMAC-SHA256 verification over the raw webhook body.
- Database uniqueness protection for Razorpay event IDs.
- Valid-transition state machine for `CREATED`, `AUTHORIZED`, `CAPTURED`, `SETTLED`, `FAILED`, `PENDING`, `UNKNOWN`, `PAYMENT_LINK_SENT`, and `ESCALATED`.
- Timeout reconciliation against Razorpay's authoritative payment status.
- Failure classifier plus three calibrated recovery predictors.
- Expected Net Value optimizer:

  $$
  EN_v(a) = P(\text{recovery} \mid a) \times \text{amount} - \text{cost} - \text{friction} - \text{risk}
  $$

- Five deterministic policy controls: unknown-state guard, amount limit, retry cap, confidence gate, and incident gate.
- Local Qwen3/Ollama explanation layer with deterministic fallback.
- Razorpay Test Mode and credential-free mock adapter.
- FastAPI APIs, Next.js operations dashboard, Prometheus metrics, and Docker Compose.

## Architecture

```text
Razorpay / Mock Webhook
          |
          v
Raw-body HMAC verification
          |
          v
Event deduplication and append-only audit
          |
          v
Payment event sequencer and state machine
          |
          +--------------------+
          |                    |
     Failed payment       UNKNOWN payment
          |                    |
          v                    v
   ML predictions       Razorpay reconciliation
          |                    |
          +---------+----------+
                    v
          Expected Net Value optimizer
                    |
          Local agent explanation
                    |
          Deterministic policy gate
                    |
          Idempotent adapter execution
                    |
          Audit timeline and dashboard
```

The repository is a modular monolith. Domain logic is separated from Razorpay integration, while PostgreSQL, Redis, FastAPI, Next.js, and Prometheus run through Docker Compose.

## Verified Benchmark

The stored evaluation artifact contains 10,000 synthetic held-out scenarios:

| Strategy | Recovery rate | Amount recovered | Mean regret/payment |
|---|---:|---:|---:|
| Fixed six-hour retry | 41.83% | ₹4,590,672.48 | ₹53.68 |
| Oracle-assisted comparator | 50.15% | ₹5,477,158.90 | ₹0.00 |
| **RAPID** | **47.23%** | **₹5,138,205.23** | **₹21.46** |

Compared with fixed retry, the artifact reports **+5.40 percentage points** recovery, **₹547,532.75** additional recovered amount per 10,000 scenarios, and **60.014%** lower decision regret. It also reports zero unknown-state errors, double-charge incidents, and policy guardrail violations.

These are synthetic evaluation results, not production guarantees. The distribution-shift artifact shows a large absolute performance drop, so robustness claims require independent data and further validation.

## Technology

| Layer | Technology |
|---|---|
| Runtime | Python 3.12+, `uv`, Hatchling |
| API | FastAPI, Uvicorn, Pydantic v2 |
| Persistence | SQLAlchemy 2, PostgreSQL 16, SQLite fallback |
| Cache/infrastructure | Redis 7 |
| ML | scikit-learn, XGBoost, NumPy, pandas |
| Agent | Ollama with Qwen3 8B/14B, deterministic mock fallback |
| Frontend | Next.js 14, React 18, TypeScript, TailwindCSS, Recharts |
| Observability | Prometheus client, OpenTelemetry dependencies, Loguru |
| Testing | pytest, Hypothesis, pytest-cov |
| Deployment | Docker Compose |

## Quick Start

### Prerequisites

- Python 3.12 or newer.
- `uv`.
- Docker Desktop and Docker Compose.
- Optional: Ollama and a local Qwen3 model.
- Optional: Razorpay Test Mode credentials.

### Install and run

```powershell
uv sync --all-extras
docker-compose up -d
make data
make train
make evaluate
python scripts/demo.py
```

Open:

- Dashboard: <http://localhost:3000>
- API: <http://localhost:8000>
- OpenAPI: <http://localhost:8000/docs>
- Prometheus: <http://localhost:9090>

Mock mode is the default and does not require Razorpay credentials or Ollama. To use Razorpay Test Mode, configure `RAZORPAY_MODE=test`, the Razorpay key values, and `RAZORPAY_WEBHOOK_SECRET` in `.env`. To use Qwen3, set `LLM_PROVIDER=ollama` and configure `OLLAMA_HOST` and `LLM_MODEL`.

## Common Commands

```powershell
make install       # Install dependencies
make data          # Generate 100K causal synthetic scenarios
make train         # Train the classifier and three recovery models
make evaluate      # Evaluate baseline, RAPID, and shift scenarios
make test          # Run the complete pytest suite
make test-unit     # Run unit tests
make test-failures # Run timeout, duplicate, and ordering tests
make test-property # Run Hypothesis property tests
make lint          # Run Ruff and Black checks
make demo          # Run the interactive demo
make up            # Start Docker Compose services
make down          # Stop Docker Compose services
```

## API Surface

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Service health and runtime configuration |
| `GET` | `/metrics` | Prometheus metrics |
| `POST` | `/webhooks/razorpay` | Verify and process Razorpay events |
| `POST` | `/api/payments` | Create a payment record |
| `GET` | `/api/payments` | List payments |
| `GET` | `/api/payments/{payment_id}` | Read payment details |
| `GET` | `/api/payments/{payment_id}/timeline` | Read the audit timeline |
| `POST` | `/api/recovery/process?payment_id=...` | Run one recovery decision |
| `POST` | `/api/recovery/reconcile` | Reconcile an unknown payment |
| `POST` | `/api/batch/recover` | Process a batch of failed payments |
| `GET` | `/api/metrics/summary` | Read live operational metrics |
| `GET` | `/api/summary` | Read live and benchmark summary |
| `POST` | `/api/demo/inject` | Inject a failure scenario |

## Repository Layout

```text
apps/api/                         FastAPI application and routers
apps/dashboard/                   Next.js operations console
packages/domain/payments/         Models, state machine, events, deduplication
packages/domain/policy/           Deterministic policy engine
packages/domain/recovery/         Revenue optimizer and health detector
packages/integrations/razorpay/   Real adapter, mock adapter, webhook handler
packages/ml/                      Simulation, features, training, evaluation
packages/workflows/               Recovery orchestrator and reconciliation
packages/utils/                   Audit logging and idempotency
scripts/                          Data, training, evaluation, and demo commands
tests/                            Unit, integration, contract, property, failure tests
docs/                             Project documentation directory
PROJECT_REPORT.md                 Detailed end-to-end technical report
docker-compose.yml                Local service topology
pyproject.toml                    Python dependencies and tool configuration
Makefile                          Developer command interface
```

## Testing

The repository covers state transitions, policy boundaries, Expected Net Value ordering, idempotency determinism, captured and settled payment invariants, unknown-state reconciliation, duplicate and out-of-order webhooks, and FastAPI health, payment, demo, and metrics endpoints.

The latest local run passed **99 tests**. The repository also contains stored benchmark and test artifacts; see [PROJECT_REPORT.md](PROJECT_REPORT.md) for the full breakdown and known warnings.

## Current Limitations

- Evaluation data is synthetic and generated from the same causal simulator used for labels.
- The runtime orchestrator currently executes payment links automatically; retry actions are recorded and escalated until a new-order retry flow is implemented.
- The default policy is global rather than merchant-specific.
- Health windows are in memory and need shared state for multiple API instances.
- Production deployment still needs migrations, replay protection, rate limiting, secret management, concurrency controls, and live Razorpay contract tests.
- The dashboard contains seeded demo defaults when the API is unavailable.

## Documentation

- [End-to-End Project Report](PROJECT_REPORT.md): architecture, workflows, APIs, data model, ML, evaluation, security review, and roadmap.

## License

MIT. See [LICENSE](LICENSE).

## Author

**Varun S**  
GitHub: [@Varun072006](https://github.com/Varun072006)
