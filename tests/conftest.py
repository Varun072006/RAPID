"""
pytest conftest — shared fixtures for all tests.

Provides:
- In-memory SQLite database (isolated per test)
- Pre-built domain objects (payments, state machine)
- Mock Razorpay adapter
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.domain.payments.models import Base, Payment, PaymentState
from packages.integrations.razorpay.mock_adapter import MockRazorpayAdapter


@pytest.fixture(scope="function")
def db() -> Session:
    """In-memory SQLite session, isolated per test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def mock_razorpay() -> MockRazorpayAdapter:
    """Mock Razorpay adapter — no real API calls."""
    return MockRazorpayAdapter()


@pytest.fixture
def failed_payment(db: Session) -> Payment:
    """A payment in FAILED state, ready for recovery."""
    payment = Payment(
        payment_id="pay_test_001",
        merchant_id="merchant_test",
        customer_id="cust_test_001",
        amount=100000,  # ₹1,000
        payment_method="card",
        bank="HDFC",
        state=PaymentState.FAILED,
        retry_count=0,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@pytest.fixture
def unknown_payment(db: Session) -> Payment:
    """A payment in UNKNOWN state (simulating API timeout)."""
    payment = Payment(
        payment_id="pay_test_002",
        merchant_id="merchant_test",
        customer_id="cust_test_002",
        amount=250000,  # ₹2,500
        payment_method="upi",
        state=PaymentState.UNKNOWN,
        razorpay_payment_id="rzp_pay_mock_abc123",
        retry_count=0,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment
