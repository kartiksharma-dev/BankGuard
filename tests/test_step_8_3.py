import asyncio
from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base
from backend.app.models.alert import Alert
from backend.app.models.customer import Customer
from backend.app.models.transaction import Transaction as TransactionModel
from backend.app.services.risk_service import score_submitted_transaction
from backend.app.services.websocket_manager import ConnectionManager, ws_manager
from simulator.preprocessing import (
    load_preprocessor,
    reset_preprocessor_cache,
    transform_transaction,
)
from simulator.schemas import Transaction


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db(monkeypatch):
    """Isolated in-memory SQLite database session."""
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


@pytest.fixture
def sample_tx() -> Transaction:
    return Transaction(
        transaction_id="TX_STEP83_001",
        customer_id="CUST_STEP83_001",
        amount=2500.0,
        merchant_category="ELECTRONICS",
        device_id="DEV_001",
        location="Mumbai",
        timestamp=datetime.now(timezone.utc),
        payment_method="UPI",
        transaction_type="PAYMENT",
        oldbalance_org=20000.0,
        newbalance_orig=17500.0,
        oldbalance_dest=10000.0,
        newbalance_dest=12500.0,
        step=1,
    )


# ---------------------------------------------------------------------------
# 1. Preprocessor Caching Tests
# ---------------------------------------------------------------------------

def test_preprocessor_loads_and_caches():
    """Preprocessor loads successfully and reuses in-memory instance."""
    reset_preprocessor_cache()
    p1 = load_preprocessor()
    assert p1 is not None

    p2 = load_preprocessor()
    # Same object reference confirms in-memory caching
    assert p1 is p2


def test_preprocessor_transformation_consistency(sample_tx):
    """Cached preprocessor produces expected 21-feature representation."""
    transformed = transform_transaction(sample_tx)
    # Scaler + One-hot outputs 21 features
    assert transformed.shape == (1, 21)


def test_preprocessor_missing_artifact_error(monkeypatch):
    """Missing preprocessor artifact raises FileNotFoundError."""
    reset_preprocessor_cache()
    non_existent = Path("non/existent/path/preprocessor.pkl")
    monkeypatch.setattr("simulator.preprocessing.PREPROCESSOR_PATH", non_existent)

    with pytest.raises(FileNotFoundError, match="Preprocessor not found"):
        load_preprocessor()

    # Restore clean state
    reset_preprocessor_cache()


# ---------------------------------------------------------------------------
# 2. Alert Evaluation & Duplicate Prevention Tests
# ---------------------------------------------------------------------------

def test_normal_transaction_no_alert(test_db, sample_tx, monkeypatch):
    """Normal transactions persist with no automatic alerts."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 0},
    )

    result = score_submitted_transaction(sample_tx)
    assert result["fraud_prediction"] == 0
    assert result["alert"] is None
    assert result["alerts"] == []

    with test_db() as db:
        alerts = db.scalars(
            select(Alert).where(Alert.transaction_id == sample_tx.transaction_id)
        ).all()
        assert len(alerts) == 0


def test_ml_fraud_only_alert(test_db, sample_tx, monkeypatch):
    """ML fraud (prediction=1) generates ML_FRAUD_DETECTED without behavioral alert."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 1},
    )

    # Low behavioral risk (0)
    result = score_submitted_transaction(
        sample_tx,
        behavioral_features={"new_device": 0, "unusual_location": 0, "high_velocity": 0},
    )

    assert result["fraud_prediction"] == 1
    assert result["alert"] is not None
    assert result["alert"]["alert_type"] == "ML_FRAUD_DETECTED"
    assert len(result["alerts"]) == 1

    with test_db() as db:
        alerts = db.scalars(
            select(Alert).where(Alert.transaction_id == sample_tx.transaction_id)
        ).all()
        assert len(alerts) == 1
        assert alerts[0].alert_type == "ML_FRAUD_DETECTED"


def test_behavioral_risk_only_alert(test_db, sample_tx, monkeypatch):
    """High behavioral risk score (>=60) triggers HIGH_BEHAVIORAL_RISK."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 0},
    )

    # Score: 20 (device) + 40 (velocity) = 60 >= 60 -> HIGH
    result = score_submitted_transaction(
        sample_tx,
        behavioral_features={"new_device": 1, "unusual_location": 0, "high_velocity": 1},
    )

    assert result["fraud_prediction"] == 0
    assert result["risk_assessment"]["behavioral_risk_score"] == 60
    assert result["alert"] is not None
    assert result["alert"]["alert_type"] == "HIGH_BEHAVIORAL_RISK"
    assert len(result["alerts"]) == 1

    with test_db() as db:
        alerts = db.scalars(
            select(Alert).where(Alert.transaction_id == sample_tx.transaction_id)
        ).all()
        assert len(alerts) == 1
        assert alerts[0].alert_type == "HIGH_BEHAVIORAL_RISK"


def test_dual_alert_generation(test_db, sample_tx, monkeypatch):
    """When both ML fraud and high behavioral risk occur, both alerts are generated."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 1},
    )

    # Score: 20 + 20 + 40 = 80 >= 60
    result = score_submitted_transaction(
        sample_tx,
        behavioral_features={"new_device": 1, "unusual_location": 1, "high_velocity": 1},
    )

    assert result["fraud_prediction"] == 1
    assert result["risk_assessment"]["behavioral_risk_score"] == 80
    assert len(result["alerts"]) == 2
    types = [a["alert_type"] for a in result["alerts"]]
    assert "ML_FRAUD_DETECTED" in types
    assert "HIGH_BEHAVIORAL_RISK" in types

    with test_db() as db:
        alerts = db.scalars(
            select(Alert).where(Alert.transaction_id == sample_tx.transaction_id)
        ).all()
        assert len(alerts) == 2


def test_duplicate_alert_prevention(test_db, sample_tx, monkeypatch):
    """Duplicate alerts of the same type for the same transaction are prevented."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 1},
    )

    # Pre-insert ML_FRAUD_DETECTED alert
    with test_db() as db:
        pre_cust = Customer(customer_id=sample_tx.customer_id)
        db.add(pre_cust)
        pre_tx = TransactionModel(
            transaction_id=sample_tx.transaction_id,
            customer_id=sample_tx.customer_id,
            amount=sample_tx.amount,
            merchant_category=sample_tx.merchant_category,
            device_id=sample_tx.device_id,
            location=sample_tx.location,
            timestamp=sample_tx.timestamp,
            payment_method=sample_tx.payment_method,
            transaction_type=sample_tx.transaction_type,
            oldbalance_org=sample_tx.oldbalance_org,
            newbalance_orig=sample_tx.newbalance_orig,
            oldbalance_dest=sample_tx.oldbalance_dest,
            newbalance_dest=sample_tx.newbalance_dest,
            step=sample_tx.step,
            fraud_prediction=1,
        )
        db.add(pre_tx)
        pre_alert = Alert(
            transaction_id=sample_tx.transaction_id,
            alert_type="ML_FRAUD_DETECTED",
            status="OPEN",
        )
        db.add(pre_alert)
        db.commit()

    # Attempting to score the duplicate transaction ID raises ValueError
    with pytest.raises(ValueError, match="already exists"):
        score_submitted_transaction(sample_tx)

    # Verify no duplicate alert was added
    with test_db() as db:
        alerts = db.scalars(
            select(Alert).where(Alert.transaction_id == sample_tx.transaction_id)
        ).all()
        assert len(alerts) == 1


# ---------------------------------------------------------------------------
# 3. Atomic Database Persistence Tests
# ---------------------------------------------------------------------------

def test_atomic_persistence_success(test_db, sample_tx, monkeypatch):
    """Customer, transaction, and alerts commit together."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 1},
    )

    score_submitted_transaction(sample_tx)

    with test_db() as db:
        cust = db.get(Customer, sample_tx.customer_id)
        tx = db.get(TransactionModel, sample_tx.transaction_id)
        alerts = db.scalars(
            select(Alert).where(Alert.transaction_id == sample_tx.transaction_id)
        ).all()

        assert cust is not None
        assert tx is not None
        assert len(alerts) == 1


def test_atomic_persistence_rollback_on_failure(test_db, sample_tx, monkeypatch):
    """Failure during persistence rolls back all database changes."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 1},
    )

    # Force an integrity error by setting an invalid flush failure
    def faulty_flush(self):
        raise RuntimeError("Simulated Database I/O Failure")

    monkeypatch.setattr("sqlalchemy.orm.Session.flush", faulty_flush)

    with pytest.raises(RuntimeError, match="Simulated Database I/O Failure"):
        score_submitted_transaction(sample_tx)

    # Ensure transaction was not persisted
    with test_db() as db:
        tx = db.get(TransactionModel, sample_tx.transaction_id)
        assert tx is None


# ---------------------------------------------------------------------------
# 4. WebSocket Broadcasting & Async API Integration Tests
# ---------------------------------------------------------------------------

def test_api_endpoint_broadcasts_events(test_db, sample_tx, monkeypatch):
    """POST /api/v1/risk/score broadcasts TRANSACTION_PROCESSED and ALERT_CREATED."""
    from backend.app.api.risk import score_transaction_endpoint

    fake_result = {
        "transaction_id": sample_tx.transaction_id,
        "customer_id": sample_tx.customer_id,
        "amount": sample_tx.amount,
        "fraud_prediction": 1,
        "risk_assessment": {"risk_level": "HIGH", "behavioral_risk_score": 20},
        "alert": {
            "alert_id": 101,
            "transaction_id": sample_tx.transaction_id,
            "alert_type": "ML_FRAUD_DETECTED",
            "status": "OPEN",
        },
        "alerts": [
            {
                "alert_id": 101,
                "transaction_id": sample_tx.transaction_id,
                "alert_type": "ML_FRAUD_DETECTED",
                "status": "OPEN",
            }
        ],
    }

    monkeypatch.setattr(
        "backend.app.api.risk.score_submitted_transaction",
        lambda tx: fake_result,
    )

    broadcasted_messages = []

    async def mock_broadcast(msg):
        broadcasted_messages.append(msg)
        return 1

    monkeypatch.setattr(ws_manager, "broadcast", mock_broadcast)

    async def scenario():
        return await score_transaction_endpoint(sample_tx)

    data = asyncio.run(scenario())

    assert data["transaction_id"] == sample_tx.transaction_id
    assert data["fraud_prediction"] == 1
    assert data["alert"] is not None

    # Verify both ALERT_CREATED and TRANSACTION_PROCESSED events were broadcast
    assert len(broadcasted_messages) == 2
    event_types = [m["type"] for m in broadcasted_messages]
    assert "ALERT_CREATED" in event_types
    assert "TRANSACTION_PROCESSED" in event_types

    # Verify transaction payload structure
    tx_event = next(m for m in broadcasted_messages if m["type"] == "TRANSACTION_PROCESSED")
    assert tx_event["data"]["transaction"]["transaction_id"] == sample_tx.transaction_id
    assert tx_event["data"]["alert"]["alert_type"] == "ML_FRAUD_DETECTED"


def test_api_endpoint_multiple_alerts_broadcasting(test_db, sample_tx, monkeypatch):
    """When dual alerts are generated, multiple ALERT_CREATED events are broadcast."""
    from backend.app.api.risk import score_transaction_endpoint

    fake_result = {
        "transaction_id": sample_tx.transaction_id,
        "customer_id": sample_tx.customer_id,
        "amount": sample_tx.amount,
        "fraud_prediction": 1,
        "risk_assessment": {"risk_level": "HIGH", "behavioral_risk_score": 80},
        "alert": {"alert_id": 201, "alert_type": "ML_FRAUD_DETECTED"},
        "alerts": [
            {"alert_id": 201, "alert_type": "ML_FRAUD_DETECTED"},
            {"alert_id": 202, "alert_type": "HIGH_BEHAVIORAL_RISK"},
        ],
    }

    monkeypatch.setattr(
        "backend.app.api.risk.score_submitted_transaction",
        lambda tx: fake_result,
    )

    broadcasted_messages = []

    async def mock_broadcast(msg):
        broadcasted_messages.append(msg)
        return 1

    monkeypatch.setattr(ws_manager, "broadcast", mock_broadcast)

    async def scenario():
        return await score_transaction_endpoint(sample_tx)

    data = asyncio.run(scenario())

    assert len(data["alerts"]) == 2
    # 2 ALERT_CREATED events + 1 TRANSACTION_PROCESSED event
    assert len(broadcasted_messages) == 3
    alert_events = [m for m in broadcasted_messages if m["type"] == "ALERT_CREATED"]
    assert len(alert_events) == 2
    alert_types = [e["data"]["alert"]["alert_type"] for e in alert_events]
    assert "ML_FRAUD_DETECTED" in alert_types
    assert "HIGH_BEHAVIORAL_RISK" in alert_types

    tx_events = [m for m in broadcasted_messages if m["type"] == "TRANSACTION_PROCESSED"]
    assert len(tx_events) == 1


def test_api_endpoint_failed_persistence_does_not_broadcast(test_db, sample_tx, monkeypatch):
    """Rejected duplicate transactions do not broadcast WebSocket events."""
    from fastapi import HTTPException
    from backend.app.api.risk import score_transaction_endpoint

    def mock_fail(tx):
        raise ValueError(f"Transaction '{tx.transaction_id}' already exists.")

    monkeypatch.setattr(
        "backend.app.api.risk.score_submitted_transaction",
        mock_fail,
    )

    broadcasted_messages = []
    monkeypatch.setattr(ws_manager, "broadcast", lambda msg: broadcasted_messages.append(msg))

    async def scenario():
        return await score_transaction_endpoint(sample_tx)

    # Duplicate request raises HTTPException 409 Conflict
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(scenario())
    assert exc_info.value.status_code == 409

    # Zero messages broadcasted on failure
    assert len(broadcasted_messages) == 0


def test_api_endpoint_non_fatal_websocket_failure(test_db, sample_tx, monkeypatch):
    """WebSocket broadcast errors do not fail the HTTP request."""
    from backend.app.api.risk import score_transaction_endpoint

    fake_result = {
        "transaction_id": sample_tx.transaction_id,
        "customer_id": sample_tx.customer_id,
        "amount": sample_tx.amount,
        "fraud_prediction": 1,
        "risk_assessment": {"risk_level": "HIGH"},
        "alert": None,
        "alerts": [],
    }

    monkeypatch.setattr(
        "backend.app.api.risk.score_submitted_transaction",
        lambda tx: fake_result,
    )

    async def failing_broadcast(msg):
        raise RuntimeError("Simulated network/WebSocket partition")

    monkeypatch.setattr(ws_manager, "broadcast", failing_broadcast)

    async def scenario():
        return await score_transaction_endpoint(sample_tx)

    response = asyncio.run(scenario())

    # Response succeeds despite WebSocket broadcast error
    assert response["transaction_id"] == sample_tx.transaction_id


def test_multiple_connected_clients_receive_broadcast():
    """ConnectionManager broadcasts payload to multiple active clients simultaneously."""
    manager = ConnectionManager()

    class MockWebSocket:
        def __init__(self, client_id):
            self.client_id = client_id
            self.received = []

        async def accept(self):
            pass

        async def send_text(self, text):
            self.received.append(text)

    clients = [MockWebSocket(f"client_{i}") for i in range(3)]

    async def scenario():
        for c in clients:
            await manager.connect(c)

        assert manager.connection_count == 3

        payload = {"type": "TRANSACTION_PROCESSED", "data": {"tx_id": "TX_MULTI_001"}}
        delivered = await manager.broadcast(payload)

        assert delivered == 3
        for c in clients:
            assert len(c.received) == 1
            assert "TX_MULTI_001" in c.received[0]

    asyncio.run(scenario())
