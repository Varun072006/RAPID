"""
Payment domain models — SQLAlchemy ORM + enums.

These are the authoritative database representations.
All business logic lives in the domain layer, NOT here.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────


class PaymentState(str, enum.Enum):
    """
    Valid states in the payment lifecycle.

    Terminal states: SETTLED (success), ESCALATED (human review required).
    UNKNOWN is a safety state — never retry without reconciliation.
    """

    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"  # Timeout / reconciliation needed
    PAYMENT_LINK_SENT = "PAYMENT_LINK_SENT"
    ESCALATED = "ESCALATED"


class RecoveryAction(str, enum.Enum):
    """Available recovery actions the system can take."""

    RETRY_NOW = "RETRY_NOW"
    RETRY_LATER = "RETRY_LATER"
    PAYMENT_LINK = "PAYMENT_LINK"
    CUSTOMER_ACTION = "CUSTOMER_ACTION"
    ESCALATE = "ESCALATE"
    DO_NOTHING = "DO_NOTHING"


class FailureMode(str, enum.Enum):
    """Inferred failure classification."""

    TRANSIENT = "transient"
    CUSTOMER_ACTION_NEEDED = "customer_action_needed"
    INFRASTRUCTURE = "infrastructure"
    CUSTOMER_ISSUE = "customer_issue"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────
# Core Tables
# ─────────────────────────────────────────────────────────────


class Payment(Base):
    """
    Core payment entity. State is the authoritative local view.
    Always reconcile with Razorpay before acting on UNKNOWN state.
    """

    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(String(64), unique=True, index=True, nullable=False)
    razorpay_payment_id = Column(String(64), nullable=True, index=True)

    # Participants
    merchant_id = Column(String(64), index=True, nullable=False)
    customer_id = Column(String(64), index=True, nullable=False)

    # Financial
    amount = Column(Integer, nullable=False)  # in paise (₹1 = 100 paise)
    currency = Column(String(3), default="INR", nullable=False)

    # Payment method
    payment_method = Column(String(32), nullable=True)  # card, upi, netbanking, wallet
    bank = Column(String(64), nullable=True)

    # State
    state = Column(Enum(PaymentState), default=PaymentState.CREATED, nullable=False)
    failure_mode = Column(String(64), nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Payment {self.payment_id} state={self.state} amount={self.amount}>"


class RecoveryDecision(Base):
    """
    Per-payment recovery decision record.
    Immutable once created — never update, only insert new decisions.
    """

    __tablename__ = "recovery_decisions"

    id = Column(Integer, primary_key=True)
    payment_id = Column(String(64), index=True, nullable=False)

    # Decision
    action = Column(Enum(RecoveryAction), nullable=False)
    predicted_probability = Column(Float, nullable=False)
    expected_value = Column(Float, nullable=False)  # in paise

    # Policy
    policy_authorized = Column(Boolean, nullable=False)
    policy_reason = Column(String(512), nullable=False)

    # Execution
    executed = Column(Boolean, default=False, nullable=False)
    execution_result = Column(String(128), nullable=True)
    idempotency_key = Column(String(64), nullable=True)

    # Agent explanation
    agent_diagnosis = Column(String(1024), nullable=True)
    agent_reason = Column(String(1024), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditEvent(Base):
    """
    Append-only audit log. Every system action recorded here.
    Full timeline replay is always possible from this table.
    """

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True)
    payment_id = Column(String(64), index=True, nullable=False)

    # Event metadata
    event_type = Column(String(64), nullable=False)
    # e.g. webhook_received, state_changed, classification, decision,
    #      policy_check, execution, reconciliation, verification

    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    details = Column(JSON, nullable=True)
    actor = Column(String(64), nullable=False)
    # e.g. system, razorpay_webhook, policy_engine, ml_model, agent, human


class WebhookReceivedEvent(Base):
    """
    Deduplication table for Razorpay webhooks.
    Unique constraint on event_id prevents double-processing.
    """

    __tablename__ = "webhook_received_events"

    id = Column(Integer, primary_key=True)
    event_id = Column(String(128), nullable=False)
    event_type = Column(String(64), nullable=False)
    raw_payload = Column(JSON, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)

    __table_args__ = (UniqueConstraint("event_id", name="uq_webhook_event_id"),)
