from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base
from backend.app.models import Customer, Transaction as TransactionModel
from backend.app.main import app
from backend.app.api import risk as risk_api
from simulator.schemas import Transaction


@pytest.fixture
def test_db(monkeypatch):
    """Create an isolated in-memory database for each test."""
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

    yield TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def sample_transaction():
    return Transaction(
        transaction_id="PERSIST-TEST-001",
        customer_id="CUSTOMER-TEST-001",
        amount=1500.0,
        merchant_category="GROCERY",
        device_id="DEVICE-TEST-001",
        location="Mumbai",
        timestamp=datetime(2026, 10, 27, 10, 30, 0),
        payment_method="UPI",
        transaction_type="PAYMENT",
        oldbalance_org=10000.0,
        newbalance_orig=8500.0,
        oldbalance_dest=5000.0,
        newbalance_dest=6500.0,
        step=1,
    )


def test_transaction_and_customer_are_persisted(
    test_db,
    sample_transaction,
    monkeypatch,
):
    monkeypatch.setattr(
        risk_api,
        "score_submitted_transaction",
        lambda transaction: __import__(
            "backend.app.services.risk_service",
            fromlist=["score_submitted_transaction"],
        ).score_submitted_transaction(transaction),
    )

    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda transaction: {"test_feature": 1},
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda features: {"fraud_prediction": 0},
    )

    from backend.app.services.risk_service import score_submitted_transaction

    result = score_submitted_transaction(sample_transaction)

    assert result["transaction_id"] == "PERSIST-TEST-001"
    assert result["fraud_prediction"] == 0

    with test_db() as db:
        saved_transaction = db.get(
            TransactionModel,
            "PERSIST-TEST-001",
        )
        saved_customer = db.get(
            Customer,
            "CUSTOMER-TEST-001",
        )

        assert saved_transaction is not None
        assert saved_transaction.fraud_prediction == 0
        assert saved_customer is not None


def test_duplicate_transaction_is_rejected(
    test_db,
    sample_transaction,
    monkeypatch,
):
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda transaction: {"test_feature": 1},
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda features: {"fraud_prediction": 0},
    )

    from backend.app.services.risk_service import score_submitted_transaction

    score_submitted_transaction(sample_transaction)

    with pytest.raises(ValueError, match="already exists"):
        score_submitted_transaction(sample_transaction)

    with test_db() as db:
        assert (
            db.query(TransactionModel)
            .filter_by(transaction_id="PERSIST-TEST-001")
            .count()
            == 1
        )


def test_duplicate_transaction_returns_http_409(
    test_db,
    sample_transaction,
    monkeypatch,
):
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda transaction: {"test_feature": 1},
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda features: {"fraud_prediction": 0},
    )

    from backend.app.services.risk_service import score_submitted_transaction

    score_submitted_transaction(sample_transaction)

    client = TestClient(app)

    response = client.post(
        "/api/v1/risk/score",
        json=sample_transaction.model_dump(mode="json"),
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]