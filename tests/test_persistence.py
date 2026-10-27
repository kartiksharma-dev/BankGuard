from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base, get_db
from backend.app.models import Customer, Transaction as TransactionModel
from backend.app.main import app
from backend.app.api import risk as risk_api
from simulator.schemas import Transaction


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

    # Make the risk service use the test database.
    monkeypatch.setattr(
        "backend.app.services.risk_service.SessionLocal",
        TestingSessionLocal,
    )

    # Make FastAPI endpoints use the same test database.
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
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def sample_transaction():
    """Return a valid transaction for persistence tests."""
    return Transaction(
        transaction_id="PERSIST-TEST-001",
        customer_id="CUSTOMER-TEST-001",
        amount=1500.0,
        merchant_category="retail",
        device_id="DEVICE-TEST-001",
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


def mock_model_predictions(monkeypatch, fraud_prediction=0):
    """Replace feature transformation and model prediction for testing."""
    import backend.app.services.risk_service as risk_service

    monkeypatch.setattr(
        risk_service,
        "transform_transaction",
        lambda transaction: {"test_feature": 1},
    )

    monkeypatch.setattr(
        risk_service,
        "predict_fraud",
        lambda features: {"fraud_prediction": fraud_prediction},
    )


def test_transaction_and_customer_are_persisted(
    test_db,
    sample_transaction,
    monkeypatch,
):
    """Verify scoring stores the transaction and its customer."""
    from backend.app.services.risk_service import score_submitted_transaction

    mock_model_predictions(monkeypatch, fraud_prediction=0)

    result = score_submitted_transaction(sample_transaction)

    assert result["transaction_id"] == sample_transaction.transaction_id
    assert result["customer_id"] == sample_transaction.customer_id
    assert result["fraud_prediction"] == 0

    with test_db() as db:
        stored_transaction = db.get(
            TransactionModel,
            sample_transaction.transaction_id,
        )
        stored_customer = db.get(
            Customer,
            sample_transaction.customer_id,
        )

        assert stored_transaction is not None
        assert stored_customer is not None
        assert stored_transaction.fraud_prediction == 0


def test_duplicate_transaction_is_rejected(
    test_db,
    sample_transaction,
    monkeypatch,
):
    """Verify that a transaction cannot be persisted twice."""
    from backend.app.services.risk_service import score_submitted_transaction

    mock_model_predictions(monkeypatch, fraud_prediction=0)

    score_submitted_transaction(sample_transaction)

    with pytest.raises(ValueError, match="already exists"):
        score_submitted_transaction(sample_transaction)

    with test_db() as db:
        transaction_count = db.scalar(
            select(func.count()).select_from(TransactionModel)
        )

        assert transaction_count == 1


def test_duplicate_transaction_returns_http_409(
    test_db,
    sample_transaction,
    monkeypatch,
):
    """Verify that duplicate transaction submissions return HTTP 409."""
    mock_model_predictions(monkeypatch, fraud_prediction=0)

    client = TestClient(app)

    payload = sample_transaction.model_dump(mode="json")

    first_response = client.post(
        "/api/v1/risk/score",
        json=payload,
    )

    assert first_response.status_code == 200

    second_response = client.post(
        "/api/v1/risk/score",
        json=payload,
    )

    assert second_response.status_code == 409
    assert "already exists" in second_response.json()["detail"]


def test_retrieve_transactions(
    test_db,
    sample_transaction,
    monkeypatch,
):
    """Verify that the retrieval endpoint returns stored transactions."""
    from backend.app.services.risk_service import score_submitted_transaction

    mock_model_predictions(monkeypatch, fraud_prediction=0)

    score_submitted_transaction(sample_transaction)

    client = TestClient(app)

    response = client.get("/api/v1/transactions")

    assert response.status_code == 200

    data = response.json()

    assert data["returned"] == 1
    assert data["limit"] == 20
    assert data["offset"] == 0

    transaction = data["items"][0]

    assert transaction["transaction_id"] == "PERSIST-TEST-001"
    assert transaction["customer_id"] == "CUSTOMER-TEST-001"
    assert transaction["fraud_prediction"] == 0


def test_filter_transactions_by_customer(
    test_db,
    sample_transaction,
    monkeypatch,
):
    """Verify retrieval can filter transactions by customer ID."""
    from backend.app.services.risk_service import score_submitted_transaction

    mock_model_predictions(monkeypatch, fraud_prediction=0)

    score_submitted_transaction(sample_transaction)

    client = TestClient(app)

    response = client.get(
        "/api/v1/transactions",
        params={"customer_id": "CUSTOMER-TEST-001"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["returned"] == 1
    assert data["items"][0]["customer_id"] == "CUSTOMER-TEST-001"

    empty_response = client.get(
        "/api/v1/transactions",
        params={"customer_id": "CUSTOMER-DOES-NOT-EXIST"},
    )

    assert empty_response.status_code == 200
    assert empty_response.json()["returned"] == 0


def test_filter_transactions_by_fraud_prediction(
    test_db,
    sample_transaction,
    monkeypatch,
):
    """Verify retrieval can filter transactions by fraud prediction."""
    from backend.app.services.risk_service import score_submitted_transaction

    mock_model_predictions(monkeypatch, fraud_prediction=1)

    score_submitted_transaction(sample_transaction)

    client = TestClient(app)

    response = client.get(
        "/api/v1/transactions",
        params={"fraud_prediction": 1},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["returned"] == 1
    assert data["items"][0]["fraud_prediction"] == 1

    legitimate_response = client.get(
        "/api/v1/transactions",
        params={"fraud_prediction": 0},
    )

    assert legitimate_response.status_code == 200
    assert legitimate_response.json()["returned"] == 0


def test_transaction_pagination(
    test_db,
    sample_transaction,
    monkeypatch,
):
    """Verify the retrieval endpoint supports limit and offset."""
    from backend.app.services.risk_service import score_submitted_transaction

    mock_model_predictions(monkeypatch, fraud_prediction=0)

    score_submitted_transaction(sample_transaction)

    second_transaction = sample_transaction.model_copy(
        update={"transaction_id": "PERSIST-TEST-002"}
    )

    score_submitted_transaction(second_transaction)

    client = TestClient(app)

    first_response = client.get(
        "/api/v1/transactions",
        params={"limit": 1, "offset": 0},
    )

    assert first_response.status_code == 200

    first_data = first_response.json()

    assert first_data["limit"] == 1
    assert first_data["offset"] == 0
    assert first_data["returned"] == 1
    assert len(first_data["items"]) == 1

    beyond_response = client.get(
        "/api/v1/transactions",
        params={"limit": 1, "offset": 2},
    )

    assert beyond_response.status_code == 200
    assert beyond_response.json()["returned"] == 0


def test_transaction_query_validation():
    """Verify invalid retrieval query parameters return HTTP 422."""
    client = TestClient(app)

    invalid_limit_response = client.get(
        "/api/v1/transactions",
        params={"limit": 101},
    )

    assert invalid_limit_response.status_code == 422

    invalid_offset_response = client.get(
        "/api/v1/transactions",
        params={"offset": -1},
    )

    assert invalid_offset_response.status_code == 422

    invalid_prediction_response = client.get(
        "/api/v1/transactions",
        params={"fraud_prediction": 2},
    )

    assert invalid_prediction_response.status_code == 422