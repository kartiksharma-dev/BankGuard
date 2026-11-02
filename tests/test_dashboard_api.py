from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base, get_db
from backend.app.main import app
from backend.app.models.customer import Customer
from backend.app.models.transaction import Transaction
from backend.app.models.alert import Alert
from backend.app.models.investigation import Investigation


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
    return TestClient(app)


def test_dashboard_stats_empty_dataset(client, test_db):
    """When no transactions exist, dashboard stats return clean zero values."""
    response = client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200

    data = response.json()
    assert data["total_transactions"] == 0
    assert data["fraud_detected"] == 0
    assert data["high_risk_transactions"] == 0
    assert data["open_alerts"] == 0
    assert data["investigations_in_progress"] == 0
    assert data["fraud_rate"] == 0.0


def test_dashboard_stats_with_data(client, test_db):
    """Dashboard stats correctly compute aggregates from stored data."""
    with test_db() as db:
        customer = Customer(customer_id="CUST-DASH-1")
        db.add(customer)
        db.flush()

        tx1 = Transaction(
            transaction_id="TX-DASH-1",
            customer_id="CUST-DASH-1",
            amount=500.0,
            merchant_category="retail",
            device_id="DEV-1",
            location="Mumbai",
            timestamp=datetime(2026, 10, 28, 12, 0, 0),
            payment_method="UPI",
            transaction_type="purchase",
            oldbalance_org=1000.0,
            newbalance_orig=500.0,
            oldbalance_dest=0.0,
            newbalance_dest=500.0,
            step=1,
            fraud_prediction=0,
        )
        tx2 = Transaction(
            transaction_id="TX-DASH-2",
            customer_id="CUST-DASH-1",
            amount=25000.0,
            merchant_category="crypto",
            device_id="DEV-2",
            location="Berlin",
            timestamp=datetime(2026, 10, 28, 12, 5, 0),
            payment_method="credit_card",
            transaction_type="transfer",
            oldbalance_org=30000.0,
            newbalance_orig=5000.0,
            oldbalance_dest=0.0,
            newbalance_dest=25000.0,
            step=1,
            fraud_prediction=1,
        )
        db.add_all([tx1, tx2])
        db.flush()

        alert = Alert(
            transaction_id="TX-DASH-2",
            alert_type="FRAUD_SUSPECTED",
            status="OPEN",
        )
        db.add(alert)
        db.flush()

        inv = Investigation(
            alert_id=alert.alert_id,
            assigned_to="analyst1",
            status="IN_PROGRESS",
            findings="Analyzing unusual geo IP",
        )
        db.add(inv)
        db.commit()

    response = client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200

    data = response.json()
    assert data["total_transactions"] == 2
    assert data["fraud_detected"] == 1
    assert data["high_risk_transactions"] >= 1
    assert data["open_alerts"] == 1
    assert data["investigations_in_progress"] == 1
    assert data["fraud_rate"] == 50.0


def test_dashboard_charts_empty_dataset(client, test_db):
    """When no transactions exist, chart endpoint returns empty lists."""
    response = client.get("/api/v1/dashboard/charts")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data["volume_by_date"], list)
    assert len(data["volume_by_date"]) == 0
    assert isinstance(data["category_distribution"], list)
    assert len(data["category_distribution"]) == 0
    assert isinstance(data["location_distribution"], list)
    assert len(data["location_distribution"]) == 0
    assert isinstance(data["risk_distribution"], list)
    