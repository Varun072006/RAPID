# Developer Guide

## Prerequisites

| Tool | Required | Install |
|------|----------|---------|
| Python 3.12+ | ✅ | [python.org](https://python.org) |
| uv | ✅ | See below |
| Docker + Docker Compose | ✅ | [docker.com](https://docker.com) |
| Ollama | Optional | [ollama.com](https://ollama.com) |
| Razorpay test keys | Optional | [razorpay.com](https://razorpay.com) |

## Installing uv

```bash
# Windows (PowerShell — run as normal user, not admin)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your terminal, then verify:
```bash
uv --version   # should print: uv 0.x.x
```

## First-Time Setup

```bash
# 1. Clone
git clone https://github.com/Varun072006/rapid-payment-recovery.git
cd rapid-payment-recovery

# 2. Configure
cp .env.example .env
# Edit .env if needed (defaults work for mock mode)

# 3. Install deps
uv sync --all-extras

# 4. Start infrastructure
docker-compose up -d db redis

# 5. Initialize DB tables
make db-init

# 6. Generate data + train models
make data
make train

# 7. Start API
uvicorn apps.api.main:app --reload

# 8. (New terminal) Start dashboard
cd apps/dashboard
npm install
npm run dev
```

## Running Without Docker

If you prefer not to use Docker:

```bash
# Install PostgreSQL and Redis locally, then:
export DATABASE_URL=postgresql://user:pass@localhost:5432/rapid_db
export REDIS_URL=redis://localhost:6379/0

# Or use SQLite for development (edit config.py)
```

## Setting Up Razorpay Test Mode (Optional)

1. Go to [https://razorpay.com](https://razorpay.com)
2. Click **Sign Up** (free, no payment required)
3. Skip KYC — test mode works immediately
4. Go to **Settings → API Keys → Generate Test Key**
5. Copy the `key_id` (starts with `rzp_test_`) and `key_secret`
6. Add to `.env`:
   ```
   RAZORPAY_KEY_ID=rzp_test_XXXXXXXX
   RAZORPAY_KEY_SECRET=XXXXXXXXXXXXXXXX
   RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
   RAZORPAY_MODE=test
   ```

## Setting Up Ollama + Qwen3 (Optional)

```bash
# 1. Install Ollama from https://ollama.com
# 2. Pull Qwen3
ollama pull qwen3:8b      # ~5GB — recommended
# ollama pull qwen3:14b   # ~9GB — better reasoning

# 3. Verify it runs
ollama run qwen3:8b "Hello, test."

# 4. Update .env
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
OLLAMA_HOST=http://localhost:11434
```

## Make Targets

| Command | Action |
|---------|--------|
| `make install` | Install all deps with uv |
| `make data` | Generate 100K scenarios |
| `make train` | Train ML models |
| `make evaluate` | Run evaluation + baselines |
| `make test` | Full test suite |
| `make test-unit` | Fast unit tests |
| `make test-failures` | Failure injection tests |
| `make test-property` | Hypothesis property tests |
| `make coverage` | HTML coverage report |
| `make demo` | Run interactive demo |
| `make lint` | ruff + black check |
| `make format` | Auto-format code |
| `make up` | Start Docker services |
| `make down` | Stop Docker services |
| `make clean` | Remove build artifacts |

## Project Layout

```
packages/domain/        ← Business logic (zero Razorpay)
packages/integrations/  ← Razorpay adapter (real + mock)
packages/ml/            ← Simulation, training, evaluation
packages/workflows/     ← Orchestrator, agent, reconciler
packages/utils/         ← Idempotency, audit
apps/api/               ← FastAPI app
apps/dashboard/         ← Next.js frontend
tests/                  ← All test suites
scripts/                ← CLI utilities
docs/                   ← Documentation
```
