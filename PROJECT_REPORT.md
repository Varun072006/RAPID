# RAPID
## End-to-End Project Report

**Revenue-optimized Autonomous Payment Intervention & Decision Engine**  
**Razorpay AI Buildathon 2026 | Track 03: AI Revenue Recovery**  
**Repository:** `Varun072006/RAPID`  
**Version:** 0.1.0  
**Report basis:** Repository source, generated evaluation artifacts, tests, and documentation inspected on 2026-09-05

---

## 1. Executive Summary

RAPID is a payment recovery platform for merchants that experience failed, delayed, duplicated, or ambiguous payment events. Its central design decision is to treat payment recovery as a correctness-constrained decision problem rather than as a simple retry scheduler.

The system combines:

- Cryptographically verified Razorpay webhooks.
- Database-backed event deduplication.
- An append-only audit trail and replayable payment timeline.
- A pure payment state machine that rejects impossible or stale transitions.
- Explicit `UNKNOWN` state handling for timeouts and ambiguous outcomes.
- A causal synthetic-data simulator and action-specific ML models.
- Expected Net Value optimization that accounts for cost, friction, and risk.
- A deterministic policy engine that is authoritative over AI proposals.
- Idempotent Razorpay Test Mode and mock execution paths.
- Local Qwen3/Ollama explanations with deterministic fallback.
- FastAPI operational APIs and a Next.js command-center dashboard.
- Prometheus metrics, Docker Compose services, and layered tests.

The safety principle is concise:

> **The model and LLM may recommend. The policy engine authorizes. The payment state machine protects financial semantics.**

The repository includes a held-out synthetic benchmark with 10,000 test scenarios. The stored benchmark reports a RAPID recovery rate of **47.23%**, compared with **41.83%** for a fixed six-hour retry baseline, an incremental recovered amount of **₹547,532.75** per 10,000 scenarios, and mean decision regret of **₹21.46** compared with **₹53.68** for the fixed retry baseline. The artifact also reports zero unknown-state errors, double-charge incidents, and policy guardrail violations. These results are synthetic and should not be treated as production validation.

This report is both a technical walkthrough and an implementation-status document. Where repository documentation and executable artifacts disagree, the current code and generated artifacts are treated as the source of truth and the discrepancy is called out.

---

## 2. Project Identity and Scope

### 2.1 Product identity

| Item | Detail |
|---|---|
| Project | RAPID |
| Expanded name | Revenue-optimized Autonomous Payment Intervention & Decision Engine |
| Domain | Payment recovery and revenue operations |
| PSP integration | Razorpay Test Mode plus deterministic mock adapter |
| Primary users | Merchant payment operations and revenue engineering teams |
| Secondary users | Finance, reconciliation, risk, and support operations |
| Runtime | Python 3.12+, FastAPI, SQLAlchemy 2, Next.js 14 dashboard |
| Packaging | `uv`, Hatchling, Make targets |
| Storage | PostgreSQL 16 in Compose; SQLite fallback/development support |
| Optional AI | Ollama with Qwen3 8B/14B |
| Observability | Prometheus client metrics and OpenTelemetry dependencies |
| License | MIT |
| Current release | 0.1.0 prototype/buildathon implementation |

### 2.2 Problem statement

Payment systems are asynchronous and only partially observable. A payment can be authorized, captured, settled, failed, pending, or ambiguous after a network timeout. A naive retry policy cannot distinguish a temporary issuer problem from an already-captured payment or a customer-side issue.

Blind retries create several classes of harm:

1. **Duplicate-charge risk:** a client timeout does not prove that the server-side capture failed.
2. **Gateway and issuer pressure:** repeated attempts can amplify an infrastructure incident.
3. **Poor unit economics:** the highest recovery probability is not necessarily the highest net revenue action.
4. **Customer friction:** repeated retries can be worse than a fresh payment link or delayed retry.
5. **Weak auditability:** an opaque automated decision is difficult to reconcile or explain.

RAPID addresses these concerns with a bounded-autonomy workflow: first establish state, then estimate outcomes, optimize economic value, authorize within policy, execute idempotently, and record the complete decision trail.

### 2.3 Scope included

- One-time payment failure recovery.
- Payment links as an alternate customer-action channel.
- Timeout reconciliation against Razorpay's authoritative payment status.
- Webhook verification, deduplication, ordering, and state application.
- Synthetic causal simulation, model training, evaluation, and distribution-shift evaluation.
- Demo scenario injection for failure modes and adversarial proposals.
- Batch recovery API.
- Operational dashboard and Prometheus endpoint.

### 2.4 Scope deliberately excluded

The repository does not implement a complete fraud engine, chargeback model, KYC flow, Kafka-scale event platform, Kubernetes deployment, or voice recovery agent. Subscription-related adapter methods and demo scenarios are present, but the central recovery orchestrator currently implements payment-link execution and escalates retry actions rather than creating a new Razorpay retry order.

---

## 3. System Goals and Design Principles

### 3.1 Goals

- Preserve payment lifecycle semantics under duplicate and out-of-order events.
- Never automatically retry an unresolved `UNKNOWN` payment.
- Make every automated action explainable and auditable.
- Optimize expected monetary value, not only probability of success.
- Keep authorization deterministic and testable.
- Keep Razorpay-specific code behind an adapter boundary.
- Support local, credential-free demos through mock mode.
- Degrade safely when ML models or Ollama are unavailable.

### 3.2 Non-goals

- Replacing Razorpay's ledger or settlement system.
- Treating LLM output as an authorization mechanism.
- Claiming production accuracy from synthetic data.
- Providing distributed, horizontally scaled event processing in the current prototype.

### 3.3 Core invariants

1. A `CAPTURED` payment cannot transition back to `FAILED`, `AUTHORIZED`, or `CREATED`.
2. `SETTLED` is terminal.
3. `UNKNOWN` can exit only through reconciliation outcomes or escalation.
4. Retry actions in `UNKNOWN` state are denied even with perfect model confidence.
5. Duplicate webhook event IDs are suppressed by a database uniqueness constraint.
6. Mutating Razorpay calls use deterministic idempotency keys.
7. Policy rules are evaluated after model/agent recommendations and before execution.
8. Every decision and execution path can be represented in the audit timeline.

---

## 4. Architecture Overview

### 4.1 Logical architecture

```text
Razorpay Webhooks / REST API / Demo Simulator
                    |
                    v
        FastAPI ingestion and API routers
                    |
       HMAC verification over raw request body
                    |
          Event ID deduplication in database
                    |
          Append-only event and audit records
                    |
             Payment event sequencer
                    |
              Pure payment state machine
                    |
       +------------+-------------+
       |                          |
  Failed payment              UNKNOWN payment
       |                          |
       v                          v
  Feature extraction       Razorpay reconciliation
       |                          |
  Failure classifier              |
       |                          |
  Three recovery predictors       |
       |                          |
  Expected Net Value optimizer    |
       |                          |
  Local agent explanation/fallback|
       |                          |
  Deterministic policy gate <----+
       |
  Idempotency key and adapter execution
       |
  Recovery decision + audit timeline
       |
  Next.js dashboard / Prometheus metrics
```

### 4.2 Layer responsibilities

| Layer | Main modules | Responsibility |
|---|---|---|
| API/application | `apps/api/` | Settings, database initialization, lifecycle, CORS, routers, health, metrics mounting |
| Domain events | `packages/domain/events/` | Immutable internal event representations |
| Payment truth | `packages/domain/payments/` | ORM models, state machine, deduplication, sequencing, event store |
| Recovery economics | `packages/domain/recovery/` | Expected Net Value selection and health/circuit-breaker logic |
| Policy | `packages/domain/policy/` | Deterministic authorization and merchant constraints |
| Razorpay integration | `packages/integrations/razorpay/` | Signature verification, REST calls, mock behavior, webhook route |
| ML | `packages/ml/` | Causal simulation, features, training, calibration, evaluation |
| Workflows | `packages/workflows/` | Recovery orchestration, local agent, timeout reconciliation |
| Utilities | `packages/utils/` | Idempotency and audit logging |
| Frontend | `apps/dashboard/` | Operational views, transaction queue, optimizer simulator, policy view, benchmarks, injection lab |
| Verification | `tests/` | Unit, integration, contract, property-based, and failure-injection coverage |
| Operations | root configs and Compose | Dependencies, containers, Prometheus, developer commands |

### 4.3 Service topology

Docker Compose defines five services:

1. **`db`**: PostgreSQL 16 Alpine with persistent `pgdata` volume.
2. **`redis`**: Redis 7 Alpine, currently provisioned for future/adjacent stateful infrastructure.
3. **`api`**: FastAPI application on port 8000, dependent on healthy PostgreSQL and Redis.
4. **`dashboard`**: Next.js application on port 3000.
5. **`prometheus`**: Prometheus 2.48 on port 9090, scraping the API metrics endpoint.

The current design is a modular monolith. The domain layer is intentionally separable, but the repository does not yet split ingestion, inference, or execution into independent services.

---

## 5. End-to-End Runtime Workflow

### 5.1 Webhook ingestion workflow

1. Razorpay sends `POST /webhooks/razorpay`.
2. The handler reads the raw request body before JSON parsing.
3. `X-Razorpay-Signature` is checked with HMAC-SHA256 and constant-time comparison.
4. The event ID is taken from `X-Razorpay-Event-Id`; if absent, a truncated raw-body SHA-256 hash is used.
5. `Deduplicator` checks the `webhook_received_events` table.
6. Duplicate events return an acknowledgement payload without reapplying business effects.
7. New events are recorded atomically and marked for processing.
8. Razorpay event names are mapped to internal states.
9. `EventSequencer` asks the state machine whether the transition is valid.
10. Valid transitions update the payment and append audit data; stale or invalid transitions are ignored safely.
11. The handler returns an acknowledgement to avoid triggering repeated provider delivery.

Supported event mapping in the current handler:

| Razorpay event | Internal target |
|---|---|
| `payment.authorized` | `AUTHORIZED` |
| `payment.captured` | `CAPTURED` |
| `payment.failed` | `FAILED` |
| `payment_link.paid` | `CAPTURED` |

### 5.2 Recovery workflow

The recovery endpoint is `POST /api/recovery/process?payment_id=<id>`.

1. Load the payment and require `FAILED` or `UNKNOWN` state.
2. Build a feature record from payment data and current fallback defaults.
3. Encode categorical features into the model representation.
4. Load the persisted failure classifier and recovery-model bundle lazily.
5. Predict failure mode and classifier confidence.
6. Predict success probability for `retry_now`, `retry_later`, and `payment_link`.
7. Evaluate all actions with the revenue optimizer.
8. Ask `RecoveryAgent` for a structured proposal and explanation.
9. Run `PolicyEngine` against the optimizer-selected action.
10. If denied, persist a non-executed recovery decision and return the denial reason.
11. If authorized, derive a deterministic idempotency key.
12. Execute a payment link through Razorpay/mock adapter, or mark retry actions as escalated for the future retry-order flow.
13. Update the payment state and retry count.
14. Persist the decision and execution result.
15. Return predictions, selected action, policy result, expected value, agent proposal, and idempotency key.

### 5.3 Timeout and unknown-state workflow

```text
Capture/API timeout
       |
       v
Local state = UNKNOWN
       |
       v
Retry actions denied by policy
       |
       v
GET /v1/payments/{payment_id}
       |
       +--> captured  -> CAPTURED; safe_to_retry = false
       |
       +--> failed    -> FAILED; safe_to_retry = true
       |
       +--> created/authorized -> PENDING; safe_to_retry = false
       |
       +--> unavailable/unrecognized -> ESCALATED; safe_to_retry = false
```

The resolver exposes both a pure lookup result and `apply_reconciliation`, which updates the local payment and appends a reconciliation audit event through the API route.

### 5.4 Batch recovery workflow

`POST /api/batch/recover` processes either an explicit list of payment IDs or up to a requested limit of failed payments. It aggregates:

- Number processed.
- Number of successful executions.
- Recovery rate.
- Gross amount attempted.
- Net expected value from executed decisions.
- Action distribution.
- Per-payment result objects and errors.

---

## 6. Payment Domain and Data Model

### 6.1 Payment lifecycle

The `PaymentState` enum contains:

`CREATED`, `AUTHORIZED`, `CAPTURED`, `SETTLED`, `FAILED`, `PENDING`, `UNKNOWN`, `PAYMENT_LINK_SENT`, and `ESCALATED`.

The state machine permits the following meaningful routes:

```text
CREATED -> AUTHORIZED -> CAPTURED -> SETTLED
   |           |           |
   +---------> FAILED <----+
                  |
                  +-> PAYMENT_LINK_SENT -> CAPTURED / FAILED / PENDING / ESCALATED

CREATED/AUTHORIZED/PENDING -> UNKNOWN
UNKNOWN -> CAPTURED / FAILED / PENDING / ESCALATED
FAILED -> ESCALATED or PAYMENT_LINK_SENT
ESCALATED -> CAPTURED or FAILED
```

The implementation intentionally rejects no-op transitions and impossible backward transitions. `SETTLED` has no outgoing transitions.

### 6.2 Persistence schema

#### `payments`

The authoritative local payment view.

- Numeric primary key plus unique indexed `payment_id`.
- Optional Razorpay payment ID.
- Merchant and customer IDs.
- Amount in paise and currency, defaulting to INR.
- Payment method and bank.
- Current SQLAlchemy `PaymentState`.
- Failure mode and retry count.
- Created and updated timestamps.

#### `recovery_decisions`

An immutable decision record intended to be inserted for each recovery attempt.

- Payment ID.
- Selected `RecoveryAction`.
- Predicted probability and expected value in paise.
- Authorization flag and policy reason.
- Execution flag, result, and idempotency key.
- Agent diagnosis and reason.
- Creation timestamp.

#### `audit_events`

Append-only operational and decision history.

- Payment ID.
- Event type and timestamp.
- JSON details.
- Actor, such as `system`, `razorpay_webhook`, `policy_engine`, `ml_model`, `agent`, or `human`.

#### `webhook_received_events`

Provider-delivery deduplication table.

- Event ID with named unique constraint `uq_webhook_event_id`.
- Event type and raw payload JSON.
- Receipt timestamp.
- Processed flag.

### 6.3 Currency and amount conventions

The system stores monetary values in paise. One rupee is represented as 100 paise. Model evaluation converts amounts to INR when producing benchmark summaries; the optimizer itself calculates expected value in paise.

### 6.4 Persistence behavior

`apps/api/database.py` creates PostgreSQL engines with connection health checks and a connection pool. If PostgreSQL initialization fails, the code logs a warning and falls back to `sqlite:///./rapid.db`. Tables are created at application startup with `Base.metadata.create_all`.

This is convenient for demos, but production deployments should use controlled migrations rather than startup-time schema creation and should fail loudly when the configured production database is unavailable.

---

## 7. Deterministic Safety and Governance

### 7.1 Five policy rules

Rules execute in order and the first denial terminates authorization.

| Rule | Current implementation | Rationale |
|---|---|---|
| Unknown-state guard | Deny actions whose name contains `retry` while state is `UNKNOWN` | Prevent duplicate captures while provider state is unresolved |
| Amount limit | Deny amounts above `max_auto_amount` | Keep high-value automation under human control |
| Retry cap | Deny retry actions at or above `max_retries` | Limit repeat attempts per payment |
| Confidence gate | For high-value payments, require configured minimum probability | Avoid low-confidence autonomous financial actions |
| Incident gate | Deny retries when health indicates an incident | Prevent retry storms during infrastructure degradation |

Default `MerchantPolicy` values:

- Maximum automatic amount: ₹25,000.
- Maximum retries: 2.
- Minimum high-value recovery confidence: 0.55.
- High-value threshold: ₹5,000.
- Unknown-state retry: permanently disabled by default.

Payment links are intentionally exempt from retry-cap and incident retry checks because they do not repeat the same banking-network attempt. They are still subject to the amount and high-value confidence rules.

### 7.2 LLM boundary

`RecoveryAgent` supports two modes:

- `mock`: deterministic selection of the highest predicted probability and a generated explanation.
- `ollama`: local Qwen3 request with JSON-only response requirements.

The agent validates required response fields and falls back when Ollama is unavailable, returns empty output, produces malformed JSON, or fails validation. The current orchestrator passes the optimizer-selected action to policy authorization; the LLM is explanatory/proposal-oriented, but the policy engine remains the final gate.

### 7.3 Idempotency

`IdempotencyKeyGenerator` derives a stable 16-character hexadecimal key from merchant ID, payment ID, and action type. The key is recorded in `recovery_decisions` and sent as `Idempotency-Key` on mutating Razorpay adapter calls.

The key prevents repeated equivalent adapter requests from creating duplicate provider-side effects. It does not by itself replace a transactionally coordinated job-claim mechanism for multiple concurrent workers; that is a production-hardening item.

### 7.4 Circuit breaker and health detection

`HealthDetector` maintains global and bank/method segmented sliding windows using deques. It classifies health as:

- `HEALTHY`: failure rate below 5%.
- `DEGRADED`: failure rate from 5% up to 15%.
- `INCIDENT`: failure rate at or above 15%.

An incident pauses retries when either the global or relevant segment is in incident state. The implementation notes that the in-memory deque is suitable for the prototype; Redis-backed shared state is required for multi-instance production deployment.

---

## 8. Razorpay Integration

### 8.1 Adapter boundary

`RazorpayAdapter` is the only production integration module that directly knows the Razorpay REST API. It uses HTTP Basic Authentication, a five-second request timeout, structured error logging, and explicit conversion of HTTP failures into `RazorpayError` where applicable.

Implemented operations include:

| Operation | Method and path | Use |
|---|---|---|
| Fetch payment | `GET /v1/payments/{id}` | Reconcile timeout/unknown state |
| Create payment link | `POST /v1/payment_links` | Execute alternate recovery channel |
| Fetch order | `GET /v1/orders/{id}` | Support retry/order flows |
| Fetch subscription | `GET /v1/subscriptions/{id}` | Subscription context |
| Retry subscription invoice | `POST /v1/subscriptions/{id}/charge` | Subscription recovery capability |

### 8.2 Mock adapter

`MockRazorpayAdapter` allows the full demo and test path to operate without provider credentials. Configuration defaults to:

```text
RAZORPAY_MODE=mock
LLM_PROVIDER=mock
```

The mock adapter is valuable for deterministic local execution, but mock success behavior is not equivalent to live Razorpay behavior and must not be used as production evidence.

### 8.3 Webhook security

The handler verifies the signature over the exact raw bytes received. It uses `hmac.compare_digest` for comparison. Missing or invalid signatures return HTTP 403, while duplicate valid events are acknowledged as deduplicated to avoid provider retry amplification.

The current handler uses dependency placeholders for the database and adapter in the router definition. The repository's API tests override the database dependency used by the payment router, but production dependency wiring for the webhook route should be reviewed before deployment. This is a concrete implementation risk to resolve rather than a documentation detail.

---

## 9. Machine Learning and Simulation

### 9.1 Data generation

`scripts/generate-data.py` creates 100,000 scenarios using `ScenarioGenerator` and a fixed seed of 42. The causal model separates hidden factors from observable features:

- Issuer health.
- Network quality.
- Customer liquidity.
- Customer intent.
- Payment persistence.
- System load.

Observable features are noisy proxies and include amount, payment method, bank, latency, error code, customer tenure, historic success rate, and churn risk. Counterfactual potential outcomes are generated for each recovery action.

The information boundary is intentional:

```text
Hidden causal factors -> Observable features -> model predictions
Hidden causal factors -> counterfactual action outcomes -> labels/evaluation only
```

The models do not receive latent factors or alternative potential outcomes at decision time.

### 9.2 Failure classifier

`train_failure.py` derives failure-mode labels from counterfactual outcome patterns and trains a `GradientBoostingClassifier`:

- 200 estimators.
- Maximum depth 5.
- Learning rate 0.05.
- Subsample 0.8.
- Four reported classes: `customer_issue`, `infrastructure`, `customer_action_needed`, and `transient`.

The stored `model_metrics.json` reports validation accuracy of **0.83**. Because the labels are inferred from the same causal simulator used to create outcomes, this is useful engineering evidence but not an external clinical-style ground-truth measurement.

### 9.3 Action-specific recovery predictors

`train_recovery.py` trains one calibrated classifier per action:

- Shared `StandardScaler` fitted only on training data.
- Logistic regression base estimator.
- Isotonic `CalibratedClassifierCV` with five folds.
- Binary target: potential outcome greater than 0.50.

Stored validation results:

| Action | Validation AUC | Brier score |
|---|---:|---:|
| `retry_now` | 0.8037 | 0.1436 |
| `retry_later` | 0.7471 | 0.1972 |
| `payment_link` | 0.8555 | 0.1098 |

The `payment_link` model is strongest on the recorded AUC and Brier score. This supports the product design in which a fresh customer-action channel can outperform repeated network attempts for some failure contexts.

### 9.4 Feature encoding

The model feature contract is centralized in `packages/ml/features/engineering.py`. Categorical values are converted to numeric maps before inference. The orchestrator currently supplies fallback values for latency, error code, customer history, and churn when those fields are not available on the stored payment record. Integrating real gateway telemetry and customer history is necessary before claiming live predictive performance.

### 9.5 Model persistence and loading

Models are serialized as pickle files under `packages/ml/models/`:

- `failure_classifier.pkl`.
- `recovery_models.pkl`.

The orchestrator loads them lazily on first recovery request and returns a service-unavailable response through the API if the artifacts are missing. Pickle artifacts must be treated as trusted deployment artifacts only; they should never be loaded from an untrusted source.

---

## 10. Revenue Optimization

### 10.1 Expected Net Value equation

For action $a$, RAPID calculates:

$$
EN_v(a) = P(\text{recovery} \mid a) \times \text{amount}
- \text{cost}(a)
- \text{friction}(a) \times \text{amount}
- \text{risk}(a) \times \text{amount}
$$

The implementation evaluates all supplied action probabilities and sorts them in descending expected net value.

### 10.2 Default action parameters

| Action | Cost | Friction | Risk |
|---|---:|---:|---:|
| `retry_now` | 5 paise | 3% | 2% |
| `retry_later` | 5 paise | 1% | 1% |
| `payment_link` | 15 paise | 12% | 0% |
| `do_nothing` | 0 | 0% | 0% |

The parameters are code-level defaults and are described as merchant-adjustable, but the current API does not yet expose per-merchant parameter configuration.

### 10.3 Why probability alone is insufficient

A payment link can have a higher predicted recovery probability while losing on expected value because of customer-action friction. For example, a delayed retry can be economically preferable even when its raw probability is lower. This makes the optimizer a transparent economic control point rather than a black-box action selector.

### 10.4 Current execution limitation

The optimizer can select `retry_now` or `retry_later`, but the current orchestrator does not create a new Razorpay order for either action. It records the action, marks the payment as `ESCALATED`, and returns a queued/escalated note. Payment-link execution is the fully implemented automatic mutation path in the orchestrator.

---

## 11. API Catalogue

### 11.1 System and metrics

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Report service status, Razorpay mode, LLM provider, and model |
| `GET` | `/metrics` | Prometheus exposition endpoint |
| `GET` | `/api/metrics/summary` | Live payment, risk, recovery, and policy counters |
| `GET` | `/api/summary` | Executive summary with live counters and stored benchmark figures |

### 11.2 Payments and timelines

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/payments` | Create a payment record; duplicate IDs return 409 |
| `GET` | `/api/payments` | List recent payments with optional state filter and limit |
| `GET` | `/api/payments/{payment_id}` | Retrieve payment details |
| `GET` | `/api/payments/{payment_id}/timeline` | Retrieve replay-ready audit timeline |

### 11.3 Recovery and reconciliation

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/recovery/process?payment_id=...` | Run one payment through recovery orchestration |
| `POST` | `/api/recovery/reconcile` | Reconcile an unknown payment with Razorpay/mock state |
| `POST` | `/api/batch/recover` | Process explicit or discovered failed payments in a batch |

### 11.4 Webhooks and demo

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/webhooks/razorpay` | Verify, deduplicate, sequence, and record Razorpay events |
| `GET` | `/api/demo/scenarios` | List supported injection scenarios |
| `POST` | `/api/demo/inject` | Create a demonstration scenario and audit events |

### 11.5 Demo scenarios

The demo router supports timeout, bank degradation, duplicate webhook, out-of-order delivery, normal recovery, adversarial LLM, subscription recovery, and checkout abandonment scenarios. The most important demonstration is adversarial autonomy: a proposed automatic action for a ₹35,000 transaction is recorded and denied by the ₹25,000 policy limit.

---

## 12. Dashboard and Operator Experience

The dashboard is a client-side Next.js application using TypeScript, TailwindCSS, Lucide icons, and Recharts. It polls live API metrics and payment records every four seconds and loads the selected payment's timeline.

Primary views include:

1. **Overview and Metrics:** operational counters, revenue at risk, recovery rate, system state, and trend visualizations.
2. **Transactions and Queue:** searchable and state-filterable payment feed with selected-payment details.
3. **Causal ML and Optimizer:** interactive amount/method/bank scenario with expected-value comparisons.
4. **Autonomy Policy Gates:** visible policy controls and safety state.
5. **ROI and Benchmarks:** baseline, oracle, and RAPID comparison figures.
6. **Simulation and Test Lab:** buttons for timeout, degradation, duplicate, ordering, normal recovery, and adversarial scenarios.

The frontend is designed as an operations console rather than a marketing page. It continues to display seeded local defaults when the backend is offline, while attempting to replace them with live data when the API is available. This is useful for demos but should be clearly labeled in a production console so placeholder values cannot be mistaken for live telemetry.

---

## 13. Observability and Operations

### 13.1 Prometheus metrics

The observability module defines counters, gauges, and histograms for:

- Webhooks received by event type.
- Duplicate webhooks suppressed.
- Recovery decisions by action and authorization.
- Recovery executions by action and success.
- Policy violations by rule.
- Reconciliation outcomes.
- Decision latency.
- Total recovered amount in paise.
- Active unknown payments.
- Current system failure rate.

Prometheus is mounted at `/metrics` through `make_asgi_app()` and a Compose Prometheus service is provided for scraping.

### 13.2 Logging

Loguru is used throughout the backend and workflow layers for lifecycle events, state transitions, model loading, policy decisions, provider failures, reconciliation, and execution. Audit events are persisted separately so operational logs and financial decision history are not the same thing.

### 13.3 Configuration

`pydantic-settings` loads `.env` values with safe mock defaults. Important settings include Razorpay credentials/mode, database URL, Redis URL, API host/port, debug flag, secret key, Ollama host/model/provider, and dashboard API URL.

The default `secret_key` and database credentials are development values. They must be replaced in any deployment beyond local development.

---

## 14. Deployment and Developer Workflow

### 14.1 Recommended local setup

```powershell
uv sync --all-extras
docker-compose up -d
make data
make train
make evaluate
python scripts/demo.py
```

Dashboard: `http://localhost:3000`  
API: `http://localhost:8000`  
OpenAPI UI: `http://localhost:8000/docs`  
Prometheus: `http://localhost:9090`

### 14.2 Make targets

| Target | Effect |
|---|---|
| `install` | Install all dependencies with uv |
| `data` | Generate 100K synthetic scenarios |
| `train` | Train classifier and recovery models |
| `evaluate` | Evaluate baselines, RAPID, and shift data |
| `test` | Run the full pytest suite |
| `test-unit` | Run unit tests |
| `test-integration` | Run API integration tests |
| `test-failures` | Run timeout, duplicate, and ordering tests |
| `test-contract` | Run payment semantic contracts |
| `test-property` | Run Hypothesis invariants |
| `coverage` | Produce terminal and HTML coverage |
| `lint` | Run Ruff and Black checks |
| `format` | Apply Ruff fixes and Black formatting |
| `demo` | Run the interactive Python demo |
| `demo-ready` | Train models if needed, then run demo |
| `db-init` | Create database tables |
| `up` / `down` | Start/stop Compose |
| `clean` | Remove generated caches, reports, models, and parquet data |

### 14.3 Container notes

The API container runs Uvicorn with reload enabled and mounts `packages/` and `apps/api/` for development. This is appropriate for a local prototype, not for a hardened production image. A production image should use a non-reload process, non-root user, pinned image/dependency versions, secret injection, migration execution, and explicit resource limits.

---

## 15. Testing Strategy

The test suite is organized around financial correctness and failure behavior rather than only happy-path API coverage.

### 15.1 Test layers

- **Unit tests:** state machine, policy engine, and revenue optimizer.
- **Contract tests:** captured/settled/unknown payment semantics.
- **Property tests:** Hypothesis checks for transition result shape, deterministic idempotency, optimizer ordering, amount limits, and retry caps.
- **Failure-injection tests:** timeouts, duplicate events, and out-of-order events.
- **Integration tests:** health, metrics, payment CRUD, demo injection, and metrics summary.

### 15.2 Recorded test result

The repository's `test_results.json` records:

| Suite | Tests | Result |
|---|---:|---|
| Full recorded total | 81 | 81 passed, 0 failed, 0 skipped |
| State machine unit suite | 27 | Passed |
| Policy unit suite | 12 | Passed |
| Optimizer unit suite | 5 | Passed |
| Payment contract suite | 5 | Passed |
| Property suite | 7 | Passed |
| Timeout failure injection | 7 | Passed |
| Duplicate failure injection | 5 | Passed |
| Out-of-order failure injection | 3 | Passed |

The recorded duration is 2.48 seconds. The artifact reports full coverage for several deterministic suites and Hypothesis coverage for property tests. The integration test file is present and should be included in the next freshly generated result if the recorded artifact predates the current test tree.

### 15.3 Testing strengths

- Critical state invariants are asserted directly.
- The policy engine is tested at boundaries, including exact amount limit and retry cap.
- The unknown-state rule is tested with high confidence to prove that confidence cannot bypass safety.
- Adversarial and provider-unavailable paths are represented.
- Deterministic idempotency is tested with generated inputs.

### 15.4 Testing gaps

- No load test for concurrent webhook deduplication across multiple API workers.
- No live-provider contract test against Razorpay Test Mode.
- No end-to-end browser automation artifact for the Next.js dashboard.
- No migration upgrade test.
- No explicit test proving webhook dependency wiring in the production application instance.
- No security test suite for replay windows, secret rotation, rate limiting, or payload-size limits.

---

## 16. Evaluation Results

### 16.1 Stored held-out benchmark

The generated `evaluation_results.json` contains 10,000 normal-distribution test scenarios.

| Strategy | Recovery rate | Amount recovered | Unnecessary interventions | Mean regret/payment |
|---|---:|---:|---:|---:|
| Fixed 6h retry | 41.83% | ₹4,590,672.48 | 5,817 / 58.17% | ₹53.68 |
| Rule-based oracle-assisted | 50.15% | ₹5,477,158.90 | 4,985 / 49.85% | ₹0.00 |
| RAPID | 47.23% | ₹5,138,205.23 | 5,277 / 52.77% | ₹21.46 |

Derived normal-distribution improvements reported by the artifact:

- Recovery-rate improvement over fixed retry: **5.40 percentage points**.
- Additional recovered amount per 10,000 scenarios: **₹547,532.75**.
- Total regret reduction: **₹322,144.66**.
- Regret reduction: **60.014%**.
- RAPID reaches approximately **94.2%** of the oracle recovery rate.

### 16.2 Safety and governance results

The stored evaluation artifact reports:

- Unknown-state errors: **0**.
- Double-charge incidents: **0**.
- Policy guardrail violations: **0**.
- Decision audit-trail coverage: **100%**.
- Circuit breaker active: **true**.

These are simulator/evaluation claims and test outcomes, not a formal production guarantee. A production guarantee would require provider contract evidence, concurrency tests, monitoring, and operational controls.

### 16.3 Distribution-shift result

The stored distribution-shift section reports a severe reduction in absolute recovery for all strategies: RAPID records **0.84%** recovery versus **0.01%** for fixed retry and **0.85%** for the oracle-assisted comparator. RAPID still reduces regret by **99.617%** relative to fixed retry in that generated slice.

This result conflicts with the older submission text that says accuracy degrades by less than 3% under a 1.5x bank-failure shift. The current report treats the JSON artifact as authoritative: the shift scenario is not a successful absolute-performance demonstration. It does demonstrate that the optimizer can preserve relative decision quality under the specific generated shift, but the shift generator, metric definition, and calibration behavior need deeper validation before calling the system robust to distribution change.

### 16.4 Evaluation limitations

- Training, validation, test, and shift data are generated from the same simulator family.
- Failure labels are inferred from counterfactual outcomes.
- The oracle-assisted baseline has access to information unavailable at decision time.
- Production outcomes include provider policies, customer behavior, fraud controls, and operational effects not present in the simulator.
- The benchmark evaluator currently chooses the highest predicted recovery probability for RAPID; the runtime orchestrator additionally uses Expected Net Value. Benchmark/runtime decision parity should be aligned before using the benchmark as a strict optimizer evaluation.

---

## 17. Security, Privacy, and Reliability Review

### 17.1 Existing controls

- Raw-body HMAC-SHA256 webhook verification.
- Constant-time signature comparison.
- Provider event ID uniqueness constraint.
- Parameterized SQLAlchemy ORM access.
- Pydantic request validation for API request bodies.
- Idempotency headers on mutating adapter calls.
- No payment credentials passed to the LLM prompt.
- Local Ollama option with no external model API requirement.
- Policy denial for high-value, ambiguous, repeated, or incident-time actions.
- Append-only audit model for reconciliation and review.

### 17.2 Risks requiring production treatment

1. **Webhook dependency wiring:** The webhook router declares placeholder dependencies and should be explicitly wired to `get_db` and a configured Razorpay adapter.
2. **Replay protection:** Signature verification authenticates a payload but the implementation does not show timestamp/age validation or replay-window enforcement.
3. **Rate limiting:** No API/webhook rate limiter is visible in the current application.
4. **Secret management:** Compose contains development database credentials and configuration defaults; production secrets need a secret manager.
5. **Concurrent execution:** A deterministic idempotency key helps provider calls, but local work claiming and decision insertion need transactional/concurrency controls for multiple workers.
6. **Schema migrations:** `create_all` is not a migration strategy.
7. **Model artifact trust:** Pickle loading requires controlled artifact provenance and integrity validation.
8. **Observability completeness:** Metrics are declared, but a complete instrumentation audit is needed to ensure every counter is incremented on all paths.
9. **PII and payment data retention:** Audit payload retention, redaction, access control, and PCI boundary need explicit policy.
10. **Retry implementation:** The selected retry actions currently escalate rather than performing a new-order workflow.

---

## 18. Repository Map

```text
RAPID/
├── apps/
│   ├── api/
│   │   ├── config.py                 Settings and environment configuration
│   │   ├── database.py               SQLAlchemy engine/session setup
│   │   ├── main.py                   FastAPI app and lifespan
│   │   ├── observability.py           Prometheus metric definitions
│   │   ├── Dockerfile                API image definition
│   │   └── routers/
│   │       ├── demo.py               Failure-injection scenarios
│   │       ├── metrics.py            Live and executive metrics
│   │       └── payments.py            Payment, recovery, batch, timeline APIs
│   └── dashboard/
│       ├── package.json              Next.js dependencies and scripts
│       ├── next.config.js             Public API configuration
│       ├── src/app/page.tsx           Main operations console
│       ├── src/app/globals.css        Global dashboard styling
│       └── Dockerfile                Dashboard image definition
├── packages/
│   ├── domain/
│   │   ├── events/events.py           Domain event structures
│   │   ├── payments/                  Models, deduplication, sequencing, store, state machine
│   │   ├── policy/engine.py            Deterministic policy gate
│   │   └── recovery/                   Optimizer and health detector
│   ├── integrations/razorpay/          Real/mock adapter and webhook handler
│   ├── ml/
│   │   ├── evaluation/                Held-out evaluator and report
│   │   ├── features/                  Feature mappings and contract
│   │   ├── simulation/                 Causal model and scenario generator
│   │   └── training/                   Failure and recovery training scripts
│   ├── utils/                          Audit and idempotency helpers
│   └── workflows/
│       ├── reconciliation/             Unknown-state resolver
│       └── recovery/                   Agent and orchestrator
├── scripts/                            Data, training, evaluation, demo commands
├── tests/                              Unit, contract, property, integration, failure injection
├── docs/                               Architecture and developer guide
├── benchmark_results.csv               Benchmark slices/results
├── evaluation_results.json             Stored normal and shift evaluation
├── model_metrics.json                  Stored validation metrics
├── test_results.json                   Stored test summary
├── docker-compose.yml                  Local service topology
├── prometheus.yml                      Prometheus scrape configuration
├── Makefile                            Developer command interface
├── pyproject.toml                      Python metadata and tool configuration
├── README.md                           Quickstart and product overview
├── SUBMISSION.md                       Buildathon submission narrative
└── RAPID_MASTER_TECHNICAL_DOSSIER.md   Existing long-form technical dossier
```

---

## 19. Strengths

1. **Correctness-first payment semantics:** The state machine and unknown-state boundary address the most dangerous failure mode directly.
2. **Deterministic governance:** AI output cannot bypass amount, retry, confidence, or incident controls.
3. **Clear economics:** Expected Net Value makes tradeoffs inspectable and tunable.
4. **Good modular boundaries:** Domain logic is separated from provider integration and workflow orchestration.
5. **Credential-free demo path:** Mock adapters and injected scenarios make the concept reproducible.
6. **Strong failure-oriented testing:** Duplicate, timeout, stale event, adversarial proposal, and property tests target the real risks.
7. **Useful operator surface:** The dashboard connects benchmark reasoning, live entities, timelines, and failure injection.
8. **Transparent limitations:** The repository documents synthetic-data caveats and deliberately omitted scope.

---

## 20. Recommended Next Steps

### Priority 0: correctness and integration

- Wire the webhook route to real FastAPI database and Razorpay dependencies.
- Add integration tests for signed webhook acceptance, invalid signatures, duplicates, and stale transitions.
- Implement a transactional recovery-job claim/idempotency boundary for concurrent workers.
- Complete the retry-now and retry-later new-order workflow, or remove those actions from automatic execution until implemented.

### Priority 1: production safety

- Add Alembic migrations and remove production reliance on `create_all`.
- Add webhook replay-window checks, payload limits, rate limiting, and secret rotation.
- Add authorization and audit access controls for merchant and customer data.
- Move health windows and job state to Redis or another shared store.
- Add trusted model artifact packaging, checksums, version metadata, and rollback support.

### Priority 2: model credibility

- Validate against anonymized production outcomes or a provider-approved representative dataset.
- Separate simulator generations for training and evaluation to reduce generator overfitting.
- Align benchmark decisions with runtime Expected Net Value rather than probability-only selection.
- Add calibration curves, confidence intervals, per-segment metrics, and explicit shift definitions.
- Add drift detection and retraining triggers.

### Priority 3: operational maturity

- Instrument every declared Prometheus metric and add alert rules.
- Add load, chaos, and multi-instance tests.
- Add Playwright dashboard smoke tests and accessibility checks.
- Replace dashboard placeholder defaults with explicit empty/offline states.
- Add CI for tests, lint, type checking, model artifact validation, and container builds.

### Priority 4: merchant configurability

- Persist merchant-specific policy and optimizer parameters.
- Support per-bank, per-method, and per-segment thresholds.
- Add approval workflows for high-value automation.
- Add campaign controls for payment-link expiry, channel preferences, and customer contact policy.

---

## 21. Final Assessment

RAPID is a thoughtfully scoped payment-recovery prototype with a credible architecture for bounded autonomy. Its strongest contribution is not the claim that an ML model can retry payments; it is the combination of state reconstruction, uncertainty handling, economic optimization, deterministic authorization, and auditability around a financial side effect.

The repository demonstrates the core idea well in mock mode and synthetic evaluation. The next engineering threshold is integration fidelity: provider-wired webhook execution, concurrent idempotent processing, completed retry-order semantics, production-grade migrations and security controls, and evaluation against real or independently generated payment data.

In its current state, RAPID is best described as:

> **A production-inspired, correctness-focused payment recovery engine and evaluation platform, with a working mock/payment-link path and a clear roadmap to production hardening.**

---

## Appendix A: Evidence Files

The report is grounded in these repository artifacts:

- `README.md`
- `RAPID_MASTER_TECHNICAL_DOSSIER.md`
- `SUBMISSION.md`
- `docs/architecture.md`
- `docs/dev-guide.md`
- `pyproject.toml`
- `docker-compose.yml`
- `Makefile`
- `apps/api/main.py`
- `apps/api/config.py`
- `apps/api/database.py`
- `apps/api/routers/payments.py`
- `apps/api/routers/metrics.py`
- `apps/api/routers/demo.py`
- `packages/domain/payments/models.py`
- `packages/domain/payments/state_machine.py`
- `packages/domain/policy/engine.py`
- `packages/domain/recovery/optimizer.py`
- `packages/domain/recovery/system_health.py`
- `packages/integrations/razorpay/adapter.py`
- `packages/integrations/razorpay/webhook_handler.py`
- `packages/workflows/recovery/orchestrator.py`
- `packages/workflows/recovery/agent.py`
- `packages/workflows/reconciliation/unknown_state.py`
- `packages/ml/simulation/causal_model.py`
- `packages/ml/training/train_failure.py`
- `packages/ml/training/train_recovery.py`
- `packages/ml/evaluation/evaluator.py`
- `evaluation_results.json`
- `model_metrics.json`
- `test_results.json`
