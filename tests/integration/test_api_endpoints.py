"""
Integration tests for FastAPI endpoints.
Verifies health, payment CRUD, demo injection, metrics, and recovery endpoints.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.database import get_db
from apps.api.main import app
from packages.domain.payments.models import Base


@pytest.fixture(scope="function")
def client() -> TestClient:
    """Test client with shared in-memory SQLite database across sessions."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


class TestSystemEndpoints:
    def test_health_endpoint(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "razorpay_mode" in data
        assert "llm_provider" in data

    def test_metrics_endpoint(self, client: TestClient):
        response = client.get("/metrics")
        assert response.status_code == 200


class TestPaymentEndpoints:
    def test_create_and_get_payment(self, client: TestClient):
        payload = {
            "payment_id": "pay_integ_001",
            "merchant_id": "merch_integ",
            "customer_id": "cust_integ",
            "amount": 150000,
            "payment_method": "upi",
            "bank": "SBI",
        }
        res_create = client.post("/api/payments", json=payload)
        assert res_create.status_code == 201
        assert res_create.json()["payment_id"] == "pay_integ_001"
        assert res_create.json()["state"] == "CREATED"

        # Conflict on duplicate
        res_dup = client.post("/api/payments", json=payload)
        assert res_dup.status_code == 409

        # Get payment detail
        res_get = client.get("/api/payments/pay_integ_001")
        assert res_get.status_code == 200
        data = res_get.json()
        assert data["amount"] == 150000
        assert data["payment_method"] == "upi"

    def test_list_payments(self, client: TestClient):
        client.post(
            "/api/payments",
            json={
                "payment_id": "pay_list_001",
                "merchant_id": "m1",
                "customer_id": "c1",
                "amount": 50000,
            },
        )
        res = client.get("/api/payments?limit=10")
        assert res.status_code == 200
        items = res.json()
        assert len(items) >= 1
        assert any(item["payment_id"] == "pay_list_001" for item in items)

    def test_get_nonexistent_payment(self, client: TestClient):
        res = client.get("/api/payments/nonexistent_id")
        assert res.status_code == 404


class TestDemoInjectionEndpoints:
    def test_list_scenarios(self, client: TestClient):
        res = client.get("/api/demo/scenarios")
        assert res.status_code == 200
        scenarios = res.json()
        assert "timeout" in scenarios
        assert "normal_recovery" in scenarios
        assert "adversarial_llm" in scenarios

    @pytest.mark.parametrize(
        "scenario",
        [
            "timeout",
            "normal_recovery",
            "adversarial_llm",
            "bank_degradation",
            "duplicate_webhook",
            "out_of_order",
        ],
    )
    def test_inject_scenarios(self, client: TestClient, scenario: str):
        res = client.post("/api/demo/inject", json={"scenario_type": scenario})
        assert res.status_code == 200
        data = res.json()
        assert data["scenario"] == scenario


class TestMetricsSummaryEndpoint:
    def test_metrics_summary(self, client: TestClient):
        client.post("/api/demo/inject", json={"scenario_type": "normal_recovery"})
        res = client.get("/api/metrics/summary")
        assert res.status_code == 200
        metrics = res.json()
        assert "total_payments" in metrics
        assert "failed_payments" in metrics
        assert "recovery_rate" in metrics
