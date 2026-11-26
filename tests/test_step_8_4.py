import asyncio
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base
from backend.app.main import app
from backend.app.models.alert import Alert
from backend.app.models.customer import Customer
from backend.app.models.transaction import Transaction as TransactionModel
from backend.app.services.simulator_service import SimulationStreamer
from backend.app.services.websocket_manager import ws_manager
from simulator.scenarios import TransactionScenario


@pytest.fixture
def test_db(monkeypatch):
    """Isolated in-memory SQLite database session fixture."""
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
def fresh_streamer():
    """Create an isolated SimulationStreamer instance that is guaranteed stopped on teardown."""
    streamer = SimulationStreamer()
    try:
        yield streamer
    finally:
        streamer.stop()


# ---------------------------------------------------------------------------
# 1. Simulation Manager Lifecycle & Configuration Tests
# ---------------------------------------------------------------------------

def test_streamer_initial_state(fresh_streamer):
    """Streamer initializes in stopped state with zeroed metrics."""
    status = fresh_streamer.get_status()
    assert status["is_running"] is False
    assert status["total_generated"] == 0
    assert status["total_successful"] == 0
    assert status["total_failed"] == 0
    assert status["total_fraud"] == 0
    assert status["total_alerts"] == 0
    assert status["started_at"] is None
    assert status["stopped_at"] is None
    assert status["generation_interval"] == 1.0


def test_streamer_start_and_stop_lifecycle(fresh_streamer):
    """Streamer starts background loop, updates timestamps, and stops cleanly."""
    status = fresh_streamer.start(generation_interval=2.0, scenario="HIGH_AMOUNT")
    assert status["is_running"] is True
    assert status["generation_interval"] == 2.0
    assert status["scenario"] == "HIGH_AMOUNT"
    assert status["started_at"] is not None
    assert status["stopped_at"] is None

    # Stop the streamer
    stopped = fresh_streamer.stop()
    assert stopped["is_running"] is False
    assert stopped["stopped_at"] is not None
    assert fresh_streamer._task is None


def test_streamer_repeated_start_prevents_duplicate_workers(fresh_streamer):
    """Calling start on an already running streamer does not spawn duplicate tasks."""
    status1 = fresh_streamer.start(generation_interval=1.5, scenario="NORMAL")
    assert status1["is_running"] is True
    initial_task = fresh_streamer._task

    # Repeated start attempt
    status2 = fresh_streamer.start(generation_interval=0.5, scenario="NEW_DEVICE")
    assert status2["is_running"] is True
    # The existing task is retained, not replaced or duplicated
    assert fresh_streamer._task is initial_task
    # Interval and scenario remain unchanged from original running state
    assert fresh_streamer.generation_interval == 1.5


def test_streamer_generation_interval_resolution(fresh_streamer):
    """Streamer safely handles generation_interval and rate_per_second parameters."""
    # Direct generation interval
    s1 = SimulationStreamer()
    s1.start(generation_interval=0.5)
    assert s1.generation_interval == 0.5
    s1.stop()

    # Via rate_per_second
    s2 = SimulationStreamer()
    s2.start(rate_per_second=4.0)
    assert s2.generation_interval == 0.25
    s2.stop()

    # Clamping bounds: max 60.0, min 0.1
    s3 = SimulationStreamer()
    s3.start(generation_interval=120.0)
    assert s3.generation_interval == 60.0
    s3.stop()


def test_streamer_graceful_cancellation(fresh_streamer):
    """Stopping the streamer cancels the background task without raising unhandled errors."""
    fresh_streamer.start(generation_interval=0.1)
    assert fresh_streamer.is_running is True

    # Immediate stop cancels the running asyncio task
    stopped = fresh_streamer.stop()
    assert stopped["is_running"] is False
    assert fresh_streamer._task is None


def test_streamer_resilience_to_processing_exceptions(fresh_streamer, monkeypatch):
    """Individual transaction processing errors increment total_failed without crashing the loop."""
    call_count = 0

    async def faulty_generate():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Simulated transient I/O failure")

    monkeypatch.setattr(fresh_streamer, "generate_and_process_transaction", faulty_generate)

    async def scenario():
        fresh_streamer.generation_interval = 0.01
        fresh_streamer.is_running = True
        # Run one iteration of the stream loop logic
        task = asyncio.create_task(fresh_streamer._stream_loop())
        await asyncio.sleep(0.05)
        fresh_streamer.stop()
        await task

    asyncio.run(scenario())

    assert call_count > 0
    assert fresh_streamer.total_failed > 0
    assert fresh_streamer.total_generated == 0
    assert "Simulated transient I/O failure" in (fresh_streamer.last_error or "")


# ---------------------------------------------------------------------------
# 2. Customer Pool & Scenario Generation Tests
# ---------------------------------------------------------------------------

def test_customer_pool_reuse_and_profile_persistence(fresh_streamer):
    """Persistent customer pool maintains 12 profiles with realistic initial state."""
    assert len(fresh_streamer.customers) == 12
    assert len(fresh_streamer.destinations) == 6

    # Verify all profiles have valid initial credentials
    for cust in fresh_streamer.customers:
        assert cust.customer_id.startswith("C1")
        assert cust.usual_device.startswith("D2")
        assert cust.usual_location is not None
        assert cust.account_balance >= 100000.0

    for dst in fresh_streamer.destinations:
        assert dst.account_id.startswith("DST8")
        assert dst.balance >= 100000.0


def test_scenario_selection_mechanisms(fresh_streamer):
    """Explicit scenarios and MIXED scenario distributions are supported."""
    for sc in [
        TransactionScenario.NORMAL,
        TransactionScenario.HIGH_AMOUNT,
        TransactionScenario.NEW_DEVICE,
        TransactionScenario.UNUSUAL_LOCATION,
        TransactionScenario.HIGH_VELOCITY,
    ]:
        fresh_streamer.active_scenario = sc.value
        assert fresh_streamer._pick_scenario() == sc

    # MIXED mode yields valid scenarios across multiple draws
    fresh_streamer.active_scenario = "MIXED"
    scenarios_drawn = {fresh_streamer._pick_scenario() for _ in range(50)}
    assert TransactionScenario.NORMAL in scenarios_drawn
    assert len(scenarios_drawn) >= 2


def test_customer_transaction_history_preservation(fresh_streamer, test_db, monkeypatch):
    """Generating transactions updates the customer's behavioral history across cycles."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 0},
    )

    customer = fresh_streamer.customers[0]
    initial_tx_count = customer.transaction_count
    initial_balance = customer.account_balance

    async def scenario():
        # Force selecting the first customer
        monkeypatch.setattr("random.choice", lambda seq: seq[0])
        await fresh_streamer.generate_and_process_transaction()

    asyncio.run(scenario())

    # Customer behavioral profile recorded the transaction
    assert customer.transaction_count == initial_tx_count + 1
    assert len(customer.transaction_history) == initial_tx_count + 1
    assert len(customer.transaction_timestamps) == initial_tx_count + 1
    assert customer.account_balance < initial_balance


# ---------------------------------------------------------------------------
# 3. Transaction Processing, Persistence & WebSocket Broadcasting Tests
# ---------------------------------------------------------------------------

def test_processing_integration_success_and_persistence(fresh_streamer, test_db, monkeypatch):
    """Transactions generated by the streamer persist to SQLite/PostgreSQL atomically."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 0},
    )

    broadcasted_messages = []
    monkeypatch.setattr(
        ws_manager,
        "broadcast",
        lambda msg: broadcasted_messages.append(msg),
    )

    async def scenario():
        return await fresh_streamer.generate_and_process_transaction()

    result = asyncio.run(scenario())

    assert fresh_streamer.total_generated == 1
    assert fresh_streamer.total_successful == 1
    assert fresh_streamer.total_failed == 0

    # Verify transaction in database
    with test_db() as db:
        tx = db.get(TransactionModel, result["transaction_id"])
        cust = db.get(Customer, result["customer_id"])
        assert tx is not None
        assert cust is not None
        assert tx.amount == result["amount"]


def test_processing_integration_automatic_alerts_and_websocket(fresh_streamer, test_db, monkeypatch):
    """Streamer generates automatic alerts and broadcasts both ALERT_CREATED and TRANSACTION_PROCESSED."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    # Force ML fraud detection
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 1},
    )

    broadcasted_messages = []

    async def mock_broadcast(msg):
        broadcasted_messages.append(msg)
        return 1

    monkeypatch.setattr(ws_manager, "broadcast", mock_broadcast)

    async def scenario():
        return await fresh_streamer.generate_and_process_transaction()

    result = asyncio.run(scenario())

    assert fresh_streamer.total_fraud == 1
    assert fresh_streamer.total_alerts == 1

    # Verify WebSocket broadcast events
    event_types = [m["type"] for m in broadcasted_messages]
    assert "ALERT_CREATED" in event_types
    assert "TRANSACTION_PROCESSED" in event_types

    alert_event = next(m for m in broadcasted_messages if m["type"] == "ALERT_CREATED")
    assert alert_event["data"]["alert"]["alert_type"] == "ML_FRAUD_DETECTED"


def test_processing_integration_failure_does_not_broadcast(fresh_streamer, test_db, monkeypatch):
    """Failed persistence does not broadcast WebSocket events and increments total_failed."""
    def faulty_transform(tx):
        raise RuntimeError("ML preprocessor failure")

    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        faulty_transform,
    )

    broadcasted_messages = []
    monkeypatch.setattr(
        ws_manager,
        "broadcast",
        lambda msg: broadcasted_messages.append(msg),
    )

    async def scenario():
        with pytest.raises(RuntimeError):
            await fresh_streamer.generate_and_process_transaction()

    asyncio.run(scenario())

    # Zero WebSocket events broadcast on failure
    assert len(broadcasted_messages) == 0
    assert fresh_streamer.total_generated == 0
    assert fresh_streamer.total_successful == 0


# ---------------------------------------------------------------------------
# 4. REST Control API Tests
# ---------------------------------------------------------------------------

def test_api_stream_start_endpoint(fresh_streamer, monkeypatch):
    """POST /api/v1/simulator/stream/start starts the simulation stream."""
    monkeypatch.setattr("backend.app.api.simulator.streamer", fresh_streamer)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/simulator/stream/start",
            json={"generation_interval": 2.5, "scenario": "HIGH_AMOUNT"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is True
        assert data["generation_interval"] == 2.5
        assert data["scenario"] == "HIGH_AMOUNT"
        assert data["started_at"] is not None
        assert fresh_streamer._task is not None
        assert isinstance(fresh_streamer._task, asyncio.Task)
        assert not fresh_streamer._task.done()


def test_api_stream_stop_endpoint(fresh_streamer, monkeypatch):
    """POST /api/v1/simulator/stream/stop stops the simulation stream."""
    monkeypatch.setattr("backend.app.api.simulator.streamer", fresh_streamer)
    with TestClient(app) as client:
        # Start first via API
        res_start = client.post(
            "/api/v1/simulator/stream/start",
            json={"generation_interval": 1.0},
        )
        assert res_start.status_code == 200
        assert fresh_streamer.is_running is True

        # Stop via API
        response = client.post("/api/v1/simulator/stream/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is False
        assert data["stopped_at"] is not None


def test_api_stream_status_endpoint(fresh_streamer, monkeypatch):
    """GET /api/v1/simulator/stream/status returns complete operational telemetry."""
    monkeypatch.setattr("backend.app.api.simulator.streamer", fresh_streamer)
    with TestClient(app) as client:
        response = client.get("/api/v1/simulator/stream/status")
        assert response.status_code == 200
        data = response.json()

        assert "is_running" in data
        assert "total_generated" in data
        assert "total_successful" in data
        assert "total_failed" in data
        assert "total_fraud" in data
        assert "total_alerts" in data
        assert "generation_interval" in data
        assert "scenario" in data
        assert "connected_clients" in data


def test_api_stream_repeated_start_handled_safely(fresh_streamer, monkeypatch):
    """Repeated start requests on active stream succeed idempotently."""
    monkeypatch.setattr("backend.app.api.simulator.streamer", fresh_streamer)
    with TestClient(app) as client:
        # First start
        res1 = client.post("/api/v1/simulator/stream/start", json={"generation_interval": 1.0})
        assert res1.status_code == 200
        assert res1.json()["is_running"] is True

        # Second start on active stream
        res2 = client.post("/api/v1/simulator/stream/start", json={"generation_interval": 5.0})
        assert res2.status_code == 200
        assert res2.json()["is_running"] is True
        # Interval preserved from running session
        assert res2.json()["generation_interval"] == 1.0


def test_api_stream_invalid_configuration_rejected(client_fixture=None):
    """Invalid interval configurations are rejected with 422 Unprocessable Entity."""
    client = TestClient(app)

    # Negative interval
    res_neg = client.post("/api/v1/simulator/stream/start", json={"generation_interval": -1.0})
    assert res_neg.status_code == 422

    # Zero interval
    res_zero = client.post("/api/v1/simulator/stream/start", json={"generation_interval": 0.0})
    assert res_zero.status_code == 422

    # Excessively large interval (> 60s)
    res_large = client.post("/api/v1/simulator/stream/start", json={"generation_interval": 999.0})
    assert res_large.status_code == 422


# ---------------------------------------------------------------------------
# 5. Shutdown Safety & Concurrency Tests
# ---------------------------------------------------------------------------

def test_stop_requested_during_active_transaction_completes_safely(fresh_streamer, test_db, monkeypatch):
    """When stop is requested during an active transaction, it finishes safely and no new transaction starts."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 0},
    )

    in_flight_event = asyncio.Event()
    continue_event = asyncio.Event()
    original_generate = fresh_streamer.generate_and_process_transaction

    async def slow_generate():
        in_flight_event.set()
        await continue_event.wait()
        return await original_generate()

    monkeypatch.setattr(fresh_streamer, "generate_and_process_transaction", slow_generate)

    async def scenario():
        fresh_streamer.generation_interval = 0.01
        fresh_streamer.is_running = True
        loop_task = asyncio.create_task(fresh_streamer._stream_loop())
        fresh_streamer._task = loop_task

        # Wait until transaction is actively in flight
        await in_flight_event.wait()
        assert fresh_streamer._current_step_task is not None

        # Request stop while transaction is processing
        fresh_streamer.stop()
        assert fresh_streamer.is_running is False

        # Allow active transaction to complete
        continue_event.set()
        await loop_task

    asyncio.run(scenario())

    # Active transaction completed safely
    assert fresh_streamer.total_generated == 1
    assert fresh_streamer.total_successful == 1
    assert fresh_streamer.total_failed == 0
    assert fresh_streamer.is_running is False
    assert fresh_streamer._task is None


def test_processing_failure_session_cleanup_and_statistics(fresh_streamer, test_db, monkeypatch):
    """Database failures trigger session rollback, leave no orphan records, and maintain statistics consistency."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 1},
    )

    def faulty_flush(self):
        raise RuntimeError("Simulated Database Flush Failure")

    monkeypatch.setattr("sqlalchemy.orm.Session.flush", faulty_flush)

    async def scenario():
        with pytest.raises(RuntimeError, match="Simulated Database Flush Failure"):
            await fresh_streamer.generate_and_process_transaction()

    asyncio.run(scenario())

    # Statistics: failed transaction is NOT counted as generated or successful
    assert fresh_streamer.total_generated == 0
    assert fresh_streamer.total_successful == 0
    assert fresh_streamer.total_fraud == 0
    assert fresh_streamer.total_alerts == 0

    # Ensure database session was rolled back and zero records were persisted
    with test_db() as db:
        txs = db.scalars(select(TransactionModel)).all()
        alerts = db.scalars(select(Alert)).all()
        assert len(txs) == 0
        assert len(alerts) == 0


def test_streamer_failed_startup_does_not_report_running(fresh_streamer, monkeypatch):
    """If task creation fails during start(), streamer reports is_running=False and sets last_error."""
    class BrokenLoop:
        def create_task(self, coro):
            raise RuntimeError("Event loop queue is full or closed")

    status = fresh_streamer.start(generation_interval=1.0, loop=BrokenLoop())

    assert status["is_running"] is False
    assert fresh_streamer.is_running is False
    assert fresh_streamer._task is None
    assert "Failed to start simulation background worker" in status["last_error"]
    assert "Event loop queue is full or closed" in status["last_error"]
    assert fresh_streamer.total_generated == 0


def test_streamer_task_generates_transactions_in_event_loop(fresh_streamer, test_db, monkeypatch):
    """Streamer loop running on an event loop actually generates transactions and updates counters."""
    monkeypatch.setattr(
        "backend.app.services.risk_service.transform_transaction",
        lambda tx: [0.0] * 21,
    )
    monkeypatch.setattr(
        "backend.app.services.risk_service.predict_fraud",
        lambda f: {"fraud_prediction": 0},
    )

    async def scenario():
        # Start streamer with very short interval (0.02s)
        loop = asyncio.get_running_loop()
        fresh_streamer.start(generation_interval=0.02, scenario="NORMAL", loop=loop)
        assert fresh_streamer.is_running is True
        assert fresh_streamer._task is not None

        # Allow worker loop to run and generate transactions
        await asyncio.sleep(0.1)

        # Stop streamer safely
        fresh_streamer.stop()
        assert fresh_streamer.is_running is False

        # Wait for task to finish
        if fresh_streamer._task:
            try:
                await asyncio.wait_for(fresh_streamer._task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

    asyncio.run(scenario())

    # Assert transactions were genuinely generated and persisted
    assert fresh_streamer.total_generated > 0
    assert fresh_streamer.total_successful > 0
    assert fresh_streamer.total_failed == 0
    assert fresh_streamer.last_error is None
    assert fresh_streamer.is_running is False


def test_streamer_stop_cancels_worker_safely(fresh_streamer, monkeypatch):
    """Stopping the simulation cancels the background task safely."""
    async def scenario():
        loop = asyncio.get_running_loop()
        fresh_streamer.start(generation_interval=10.0, scenario="NORMAL", loop=loop)
        assert fresh_streamer.is_running is True
        assert fresh_streamer._task is not None
        task = fresh_streamer._task

        # Stop while sleeping
        stopped_status = fresh_streamer.stop()
        assert stopped_status["is_running"] is False
        assert fresh_streamer.is_running is False

        # Allow cancellation to propagate
        await asyncio.sleep(0.01)
        assert task.cancelled() or task.done()

    asyncio.run(scenario())


