from datetime import datetime
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base
from backend.app.models.alert import Alert
from backend.app.models.customer import Customer
from backend.app.models.transaction import Transaction as TransactionModel
from backend.app.services.risk_service import score_submitted_transaction
from simulator.schemas import Transaction


@pytest.fixture
def test_db(monkeypatch):
    """Create an isolated in-memory SQLite database for testing."""
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

    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def make_test_tx(tx_id: str = "TX-AUTO-1", customer_id: str = "C-AUTO-1") -> Transaction:
    return Transaction(
        transaction_id=tx_id,
        customer_id=customer_id,
        amount=1500.0,
        merchant_category="ELECTRONICS",
        device_id="DEV-1",
        location="Mumbai",
        timestamp=datetime(2026, 11, 2, 12, 0, 0),
        payment_method="UPI",
        transaction_type="PAYMENT",
        oldbalance_org=10000.0,
        newbalance_orig=8500.0,
        oldbalance_dest=5000.0,
        newbalance_dest=6500.0,
        step=1,
    )


def test_normal_transaction_no_alert(test_db, monkeypatch):
    """Legitimate transactions persist without generating alerts."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda features: {"fraud_prediction": 0},
    )

    tx = make_test_tx("TX-NORMAL-1")
    result = score_submitted_transaction(tx)

    assert result["fraud_prediction"] == 0
    assert result["risk_assessment"]["risk_level"] == "LOW"
    assert result["alert"] is None

    with test_db() as db:
        alerts = db.scalars(select(Alert).where(Alert.transaction_id == "TX-NORMAL-1")).all()
        assert len(alerts) == 0


def test_ml_fraud_generates_auto_alert(test_db, monkeypatch):
    """XGBoost fraud predictions trigger automatic alert creation."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda features: {"fraud_prediction": 1},
    )

    tx = make_test_tx("TX-FRAUD-1")
    result = score_submitted_transaction(tx)

    assert result["fraud_prediction"] == 1
    assert result["risk_assessment"]["risk_level"] == "HIGH"
    assert result["alert"] is not None
    assert result["alert"]["alert_type"] == "ML_FRAUD_DETECTED"
    assert result["alert"]["status"] == "OPEN"

    with test_db() as db:
        saved_alert = db.scalar(
            select(Alert).where(Alert.transaction_id == "TX-FRAUD-1")
        )
        assert saved_alert is not None
        assert saved_alert.alert_type == "ML_FRAUD_DETECTED"
        assert saved_alert.status == "OPEN"


def test_high_behavioral_risk_generates_auto_alert(test_db, monkeypatch):
    """Transactions with high behavioral risk score trigger automatic alerts."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda features: {"fraud_prediction": 0},
    )

    # Behavioral score: 20 (device) + 20 (location) + 40 (velocity) = 80 >= 60 -> HIGH
    behavioral_features = {
        "new_device": 1,
        "unusual_location": 1,
        "high_velocity": 1,
    }

    tx = make_test_tx("TX-BEHAVIORAL-1")
    result = score_submitted_transaction(tx, behavioral_features=behavioral_features)

    assert result["fraud_prediction"] == 0
    assert result["risk_assessment"]["risk_level"] == "HIGH"
    assert result["alert"] is not None
    assert result["alert"]["alert_type"] == "HIGH_BEHAVIORAL_RISK"
    assert result["alert"]["status"] == "OPEN"

    with test_db() as db:
        saved_alert = db.scalar(
            select(Alert).where(Alert.transaction_id == "TX-BEHAVIORAL-1")
        )
        assert saved_alert is not None
        assert saved_alert.alert_type == "HIGH_BEHAVIORAL_RISK"
        assert saved_alert.status == "OPEN"
