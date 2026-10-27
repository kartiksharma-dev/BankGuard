from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base, get_db
from backend.app.main import app
from backend.app.models import Alert
from backend.app.services.risk_service import score_submitted_transaction
from simulator.schemas import Transaction

from tests.test_persistence import mock_model_predictions


@pytest.fixture
def test_db(monkeypatch):
    """Create an isolated in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(
        "backend.app.services.risk_service.SessionLocal",
        TestingSessionLocal,
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setitem(
        app.dependency_overrides,
        get_db,
        override_get_db,
    )

    try:
        yield TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_transaction():
    """Return a valid transaction for alert tests."""
    return Transaction(
        transaction_id="ALERT-TEST-001",
        customer_id="ALERT-CUSTOMER-001",
        amount=1500.0,
        merchant_category="retail",
        device_id="ALERT-DEVICE-001",
        location="Ujjain",
        timestamp=datetime(2026, 10, 25, 10, 30, 0),
        payment_method="credit_card",
        transaction_type="purchase",
        oldbalance_org=5000.0,
        newbalance_orig=3500.0,
        oldbalance_dest=1000.0,
        newbalance_dest=2500.0,
        step=1,
    )


@pytest.fixture
def persisted_transaction(
    test_db,
    sample_transaction,
    monkeypatch,
):
    """Persist a transaction in the isolated test database."""
    mock_model_predictions(monkeypatch, fraud_prediction=0)
    score_submitted_transaction(sample_transaction)
    return sample_transaction


def test_create_alert_for_existing_transaction(
    client,
    persisted_transaction,
    test_db,
):
    """Creating an alert for an existing transaction returns HTTP 201."""
    response = client.post(
        "/api/v1/alerts",
        json={
            "transaction_id": persisted_transaction.transaction_id,
            "alert_type": "FRAUD_SUSPECTED",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["alert_id"] > 0
    assert data["transaction_id"] == persisted_transaction.transaction_id
    assert data["alert_type"] == "FRAUD_SUSPECTED"
    assert data["status"] == "OPEN"
    assert "created_at" in data

    with test_db() as db:
        saved_alert = db.get(Alert, data["alert_id"])
        assert saved_alert is not None
        assert (
            saved_alert.transaction_id
            == persisted_transaction.transaction_id
        )


def test_create_alert_for_missing_transaction_returns_404(client):
    """Creating an alert for a nonexistent transaction returns HTTP 404."""
    response = client.post(
        "/api/v1/alerts",
        json={
            "transaction_id": "TRANSACTION-DOES-NOT-EXIST",
            "alert_type": "FRAUD_SUSPECTED",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Transaction not found."


def test_get_alerts_returns_saved_alerts(
    client,
    persisted_transaction,
):
    """The retrieval endpoint returns saved alerts."""
    created = client.post(
        "/api/v1/alerts",
        json={
            "transaction_id": persisted_transaction.transaction_id,
            "alert_type": "FRAUD_SUSPECTED",
        },
    )

    assert created.status_code == 201

    response = client.get("/api/v1/alerts")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["alert_id"] == created.json()["alert_id"]


def test_filter_alerts_by_transaction_id(
    client,
    persisted_transaction,
):
    """Alerts can be filtered by transaction ID."""
    created = client.post(
        "/api/v1/alerts",
        json={
            "transaction_id": persisted_transaction.transaction_id,
            "alert_type": "FRAUD_SUSPECTED",
        },
    )

    assert created.status_code == 201

    response = client.get(
        "/api/v1/alerts",
        params={
            "transaction_id": persisted_transaction.transaction_id,
        },
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert (
        response.json()[0]["transaction_id"]
        == persisted_transaction.transaction_id
    )

    empty_response = client.get(
        "/api/v1/alerts",
        params={"transaction_id": "TRANSACTION-NOT-FOUND"},
    )

    assert empty_response.status_code == 200
    assert empty_response.json() == []


def test_filter_alerts_by_status(
    client,
    persisted_transaction,
):
    """Alerts can be filtered by status."""
    created = client.post(
        "/api/v1/alerts",
        json={
            "transaction_id": persisted_transaction.transaction_id,
            "alert_type": "FRAUD_SUSPECTED",
        },
    )

    assert created.status_code == 201

    open_response = client.get(
        "/api/v1/alerts",
        params={"status": "OPEN"},
    )

    assert open_response.status_code == 200
    assert len(open_response.json()) == 1
    assert open_response.json()[0]["status"] == "OPEN"

    closed_response = client.get(
        "/api/v1/alerts",
        params={"status": "CLOSED"},
    )

    assert closed_response.status_code == 200
    assert closed_response.json() == []


def test_get_alert_by_id(client, persisted_transaction):
    """A saved alert can be retrieved by its ID."""
    created = client.post(
        "/api/v1/alerts",
        json={
            "transaction_id": persisted_transaction.transaction_id,
            "alert_type": "FRAUD_SUSPECTED",
        },
    )

    assert created.status_code == 201

    alert_id = created.json()["alert_id"]

    response = client.get(f"/api/v1/alerts/{alert_id}")

    assert response.status_code == 200
    assert response.json()["alert_id"] == alert_id
    assert (
        response.json()["transaction_id"]
        == persisted_transaction.transaction_id
    )


def test_get_missing_alert_returns_404(client):
    """Requesting a nonexistent alert returns HTTP 404."""
    response = client.get("/api/v1/alerts/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Alert not found."


def test_alert_request_validation(client):
    """Invalid payloads and query parameters return HTTP 422."""
    missing_field_response = client.post(
        "/api/v1/alerts",
        json={"transaction_id": "TRANSACTION-001"},
    )

    assert missing_field_response.status_code == 422

    empty_transaction_id_response = client.post(
        "/api/v1/alerts",
        json={
            "transaction_id": "",
            "alert_type": "FRAUD_SUSPECTED",
        },
    )

    assert empty_transaction_id_response.status_code == 422

    invalid_limit_response = client.get(
        "/api/v1/alerts",
        params={"limit": 101},
    )

    assert invalid_limit_response.status_code == 422

    invalid_offset_response = client.get(
        "/api/v1/alerts",
        params={"offset": -1},
    )

    assert invalid_offset_response.status_code == 422


def test_alert_pagination(
    client,
    persisted_transaction,
):
    """Alert retrieval supports limit and offset."""
    for alert_type in ("FRAUD_SUSPECTED", "HIGH_RISK"):
        response = client.post(
            "/api/v1/alerts",
            json={
                "transaction_id": persisted_transaction.transaction_id,
                "alert_type": alert_type,
            },
        )

        assert response.status_code == 201

    first_page = client.get(
        "/api/v1/alerts",
        params={"limit": 1, "offset": 0},
    )

    assert first_page.status_code == 200
    assert len(first_page.json()) == 1

    beyond_page = client.get(
        "/api/v1/alerts",
        params={"limit": 1, "offset": 2},
    )

    assert beyond_page.status_code == 200
    assert beyond_page.json() == []