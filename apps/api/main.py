"""
FastAPI application entry point.

Startup sequence:
1. Load settings
2. Initialize DB (create tables)
3. Wire dependencies (Razorpay adapter, ML models, policy engine)
4. Register routers
5. Expose /health and /metrics endpoints
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_client import make_asgi_app

from apps.api.config import get_settings
from apps.api.database import init_db
from apps.api.routers import demo, metrics, payments
from packages.integrations.razorpay.webhook_handler import router as webhook_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    logger.info("RAPID starting up...")
    logger.info(f"  Razorpay mode: {settings.razorpay_mode.upper()}")
    logger.info(f"  LLM provider:  {settings.llm_provider.upper()} ({settings.llm_model})")
    logger.info(f"  Debug:         {settings.debug}")

    # Initialize database (create tables if not exist)
    init_db()
    logger.info("  Database initialized ✓")

    if settings.use_mock_razorpay:
        logger.warning(
            "  ⚠ Running in MOCK mode — no real Razorpay API calls. "
            "Set RAZORPAY_MODE=test and add real keys to use Test Mode."
        )

    yield

    logger.info("RAPID shutting down...")


app = FastAPI(
    title="RAPID — Payment Recovery Engine",
    description=(
        "Autonomous payment recovery engine for Razorpay. "
        "Razorpay AI Buildathon 2026 — Track 03."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus metrics endpoint ──────────────────────────────────
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# ── Routers ─────────────────────────────────────────────────────
app.include_router(payments.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(demo.router, prefix="/api")
app.include_router(webhook_router)


# ── Health ──────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "razorpay_mode": settings.razorpay_mode,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
    }
