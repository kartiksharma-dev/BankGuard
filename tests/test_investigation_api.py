from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base, get_db
from backend.app.main import app
from backend.app.models import Alert, Customer, Transaction as TransactionModel
from backend.app.models import Investigation
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
def persisted_alert(test_db):
    """Create a customer, transaction, and alert in the test database."""
    with test_db() as db:
        customer = Customer(customer_id="INV-TEST-CUSTOMER")
        db.add(customer)
        db.flush()

        transaction = TransactionModel(
            transaction_id="INV-TEST-TRANSACTION",
            customer_id=customer.customer_id,
            amount=1500.0,
            merchant_category="retail",
            device_id="INV-TEST-DEVICE",
            location="Ujjain",
            timestamp=datetime(2026, 10, 25, 10, 30, 0),
            payment_method="credit_card",
            transaction_type="purchase",
            oldbalance_org=5000.0,
            newbalance_orig=3500.0,
            oldbalance_dest=1000.0,
            newbalance_dest=2500.0,
            step=1,
            fraud_prediction=0,
        )
        db.add(transaction)
        db.flush()

        alert = Alert(
            transaction_id=transaction.transaction_id,
            alert_type="FRAUD_SUSPECTED",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        return alert.alert_id


def test_create_investigation_for_existing_alert(
    client,
    persisted_alert,
    test_db,
):
    """Creating an investigation for an existing alert returns HTTP 201."""
    response = client.post(
        "/api/v1/investigations",
        json={
            "alert_id": persisted_alert,
            "assigned_to": "fraud_analyst_01",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["investigation_id"] > 0
    assert data["alert_id"] == persisted_alert
    assert data["assigned_to"] == "fraud_analyst_01"
    assert data["status"] == "OPEN"
    assert data["findings"] is None
    assert "created_at" in data
    assert "updated_at" in data

    with test_db() as db:
        saved = db.get(Investigation, data["investigation_id"])
        assert saved is not None
        assert saved.alert_id == persisted_alert


def test_create_investigation_for_missing_alert_returns_404(client):
    """Creating an investigation for a missing alert returns HTTP 404."""
    response = client.post(
        "/api/v1/investigations",
        json={
            "alert_id": 999999,
            "assigned_to": "fraud_analyst_01",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Alert not found."


def test_duplicate_investigation_returns_409(
    client,
    persisted_alert,
):
    """Only one investigation may exist for an alert."""
    payload = {
        "alert_id": persisted_alert,
        "assigned_to": "fraud_analyst_01",
    }

    first_response = client.post(
        "/api/v1/investigations",
        json=payload,
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/investigations",
        json=payload,
    )

    assert second_response.status_code == 409


def test_get_investigations(
    client,
    persisted_alert,
):
    """The list endpoint returns saved investigations."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    )
    assert created.status_code == 201

    response = client.get("/api/v1/investigations")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["alert_id"] == persisted_alert


def test_filter_investigations_by_alert_id(
    client,
    persisted_alert,
):
    """Investigations can be filtered by alert ID."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    )
    assert created.status_code == 201

    response = client.get(
        "/api/v1/investigations",
        params={"alert_id": persisted_alert},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["alert_id"] == persisted_alert

    missing_response = client.get(
        "/api/v1/investigations",
        params={"alert_id": 999999},
    )

    assert missing_response.status_code == 200
    assert missing_response.json() == []


def test_filter_investigations_by_status_and_assignee(
    client,
    persisted_alert,
):
    """Investigations can be filtered by status and assignee."""
    created = client.post(
        "/api/v1/investigations",
        json={
            "alert_id": persisted_alert,
            "assigned_to": "fraud_analyst_01",
        },
    )
    assert created.status_code == 201

    status_response = client.get(
        "/api/v1/investigations",
        params={"status": "OPEN"},
    )

    assert status_response.status_code == 200
    assert len(status_response.json()) == 1

    assignee_response = client.get(
        "/api/v1/investigations",
        params={"assigned_to": "fraud_analyst_01"},
    )

    assert assignee_response.status_code == 200
    assert len(assignee_response.json()) == 1

    missing_assignee_response = client.get(
        "/api/v1/investigations",
        params={"assigned_to": "unknown_analyst"},
    )

    assert missing_assignee_response.status_code == 200
    assert missing_assignee_response.json() == []


def test_get_investigation_by_id(
    client,
    persisted_alert,
):
    """A saved investigation can be retrieved by ID."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    )
    assert created.status_code == 201

    investigation_id = created.json()["investigation_id"]

    response = client.get(
        f"/api/v1/investigations/{investigation_id}"
    )

    assert response.status_code == 200
    assert response.json()["investigation_id"] == investigation_id
    assert response.json()["alert_id"] == persisted_alert


def test_get_missing_investigation_returns_404(client):
    """A nonexistent investigation returns HTTP 404."""
    response = client.get("/api/v1/investigations/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Investigation not found."


def test_update_investigation_status_and_findings(
    client,
    persisted_alert,
):
    """Status and findings can be updated."""
    created = client.post(
        "/api/v1/investigations",
        json={
            "alert_id": persisted_alert,
            "assigned_to": "fraud_analyst_01",
        },
    )
    assert created.status_code == 201

    investigation_id = created.json()["investigation_id"]

    response = client.patch(
        f"/api/v1/investigations/{investigation_id}",
        json={
            "status": "IN_PROGRESS",
            "findings": "Further verification is required.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "IN_PROGRESS"
    assert data["findings"] == "Further verification is required."
    assert data["assigned_to"] == "fraud_analyst_01"


def test_update_investigation_assignee(
    client,
    persisted_alert,
):
    """The assigned analyst can be updated."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    )
    assert created.status_code == 201

    investigation_id = created.json()["investigation_id"]

    response = client.patch(
        f"/api/v1/investigations/{investigation_id}",
        json={"assigned_to": "fraud_analyst_02"},
    )

    assert response.status_code == 200
    assert response.json()["assigned_to"] == "fraud_analyst_02"


def test_update_missing_investigation_returns_404(client):
    """Updating a nonexistent investigation returns HTTP 404."""
    response = client.patch(
        "/api/v1/investigations/999999",
        json={"status": "IN_PROGRESS"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Investigation not found."


def test_update_investigation_with_empty_body_returns_422(
    client,
    persisted_alert,
):
    """An empty update body is rejected."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    )
    assert created.status_code == 201

    investigation_id = created.json()["investigation_id"]

    response = client.patch(
        f"/api/v1/investigations/{investigation_id}",
        json={},
    )

    assert response.status_code == 422


def test_investigation_request_validation(client):
    """Invalid request payloads and query parameters return HTTP 422."""
    invalid_alert_response = client.post(
        "/api/v1/investigations",
        json={"alert_id": 0},
    )
    assert invalid_alert_response.status_code == 422

    missing_alert_response = client.post(
        "/api/v1/investigations",
        json={},
    )
    assert missing_alert_response.status_code == 422

    invalid_limit_response = client.get(
        "/api/v1/investigations",
        params={"limit": 101},
    )
    assert invalid_limit_response.status_code == 422

    invalid_offset_response = client.get(
        "/api/v1/investigations",
        params={"offset": -1},
    )
    assert invalid_offset_response.status_code == 422

    invalid_alert_id_response = client.get(
        "/api/v1/investigations",
        params={"alert_id": 0},
    )
    assert invalid_alert_id_response.status_code == 422


def test_investigation_pagination(
    client,
    test_db,
):
    """Investigation listing supports limit and offset."""
    with test_db() as db:
        customer = Customer(customer_id="INV-PAGE-CUSTOMER")
        db.add(customer)
        db.flush()

        transaction = TransactionModel(
            transaction_id="INV-PAGE-TRANSACTION",
            customer_id=customer.customer_id,
            amount=1000.0,
            merchant_category="retail",
            device_id="INV-PAGE-DEVICE",
            location="Ujjain",
            timestamp=datetime(2026, 10, 25, 10, 30, 0),
            payment_method="credit_card",
            transaction_type="purchase",
            oldbalance_org=5000.0,
            newbalance_orig=4000.0,
            oldbalance_dest=1000.0,
            newbalance_dest=2000.0,
            step=1,
            fraud_prediction=0,
        )
        db.add(transaction)
        db.flush()

        first_alert = Alert(
            transaction_id=transaction.transaction_id,
            alert_type="FRAUD_SUSPECTED",
        )
        second_alert = Alert(
            transaction_id=transaction.transaction_id,
            alert_type="HIGH_RISK",
        )
        db.add_all([first_alert, second_alert])
        db.flush()

        db.add_all(
            [
                Investigation(alert_id=first_alert.alert_id),
                Investigation(alert_id=second_alert.alert_id),
            ]
        )
        db.commit()

    first_page = client.get(
        "/api/v1/investigations",
        params={"limit": 1, "offset": 0},
    )

    assert first_page.status_code == 200
    assert len(first_page.json()) == 1

    beyond_page = client.get(
        "/api/v1/investigations",
        params={"limit": 1, "offset": 2},
    )

    assert beyond_page.status_code == 200
    assert beyond_page.json() == []