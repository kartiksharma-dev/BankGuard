import pytest

from backend.app.services.simulator_service import SimulationStreamer
from simulator.scenarios import TransactionScenario


def test_simulation_streamer_initial_status():
    """Streamer initializes with idle status and clean metrics."""
    streamer = SimulationStreamer()
    status = streamer.get_status()

    assert status["is_running"] is False
    assert status["total_generated"] == 0
    assert status["total_fraud"] == 0
    assert status["total_alerts"] == 0
    assert status["last_error"] is None
    assert status["started_at"] is None


def test_simulation_streamer_start_and_stop():
    """Streamer toggles running state and configures interval."""
    streamer = SimulationStreamer()

    status = streamer.start(rate_per_second=2.5, scenario="HIGH_AMOUNT")
    assert status["is_running"] is True
    assert status["rate_per_second"] == 2.5
    assert status["scenario"] == "HIGH_AMOUNT"
    assert status["started_at"] is not None

    # Idempotent start
    status2 = streamer.start(rate_per_second=5.0)
    assert status2["is_running"] is True

    # Stop
    stopped_status = streamer.stop()
    assert stopped_status["is_running"] is False
    assert streamer._task is None


def test_simulation_streamer_pick_scenario():
    """Streamer properly returns designated or mixed scenarios."""
    streamer = SimulationStreamer()

    streamer.active_scenario = "NEW_DEVICE"
    assert streamer._pick_scenario() == TransactionScenario.NEW_DEVICE

    streamer.active_scenario = "UNUSUAL_LOCATION"
    assert streamer._pick_scenario() == TransactionScenario.UNUSUAL_LOCATION

    streamer.active_scenario = "MIXED"
    picked = streamer._pick_scenario()
    assert isinstance(picked, TransactionScenario)


def test_simulation_streamer_customer_pool():
    """Streamer maintains a realistic pool of customers and destinations."""
    streamer = SimulationStreamer()
    assert len(streamer.customers) == 12
    assert len(streamer.destinations) == 6
    assert all(c.account_balance > 0 for c in streamer.customers)
    assert all(d.balance > 0 for d in streamer.destinations)
