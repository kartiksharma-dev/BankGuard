import asyncio
from datetime import datetime, timezone
import logging
import random
from typing import Any

from backend.app.services.risk_service import process_and_broadcast_transaction
from backend.app.services.websocket_manager import ws_manager
from simulator.behavioral_features import calculate_behavioral_features
from simulator.customer import CustomerProfile, DestinationAccount
from simulator.generator import LOCATIONS, generate_transaction
from simulator.scenarios import TransactionScenario

logger = logging.getLogger(__name__)


class SimulationStreamer:
    """
    Manages an in-process, non-blocking background transaction generation stream.
    Cycles through an active customer pool to simulate realistic banking transactions,
    scores them through ML + behavioral heuristic models, persists to PostgreSQL,
    generates automatic fraud alerts, and broadcasts telemetry to WebSocket clients.
    """

    def __init__(self) -> None:
        self.is_running: bool = False
        self.generation_interval: float = 1.0
        self.active_scenario: str = "MIXED"
        self._task: asyncio.Task | None = None
        self._current_step_task: asyncio.Task | None = None

        # Statistics
        self.total_generated: int = 0
        self.total_successful: int = 0
        self.total_failed: int = 0
        self.total_fraud: int = 0
        self.total_alerts: int = 0
        self.last_error: str | None = None
        self.started_at: datetime | None = None
        self.stopped_at: datetime | None = None

        # Simulated customer pool (12 persistent customer profiles)
        self.customers: list[CustomerProfile] = []
        self.destinations: list[DestinationAccount] = []
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Initialize a persistent pool of simulated customers and destinations."""
        self.customers = [
            CustomerProfile(
                customer_id=f"C{1000 + i}",
                usual_device=f"D{200 + i}",
                usual_location=LOCATIONS[i % len(LOCATIONS)],
                account_balance=150000.0,
            )
            for i in range(12)
        ]
        self.destinations = [
            DestinationAccount(account_id=f"DST{8000 + j}", balance=200000.0)
            for j in range(6)
        ]

    def _pick_scenario(self) -> TransactionScenario:
        """Select a scenario based on the active mode."""
        if self.active_scenario != "MIXED":
            try:
                return TransactionScenario(self.active_scenario)
            except ValueError:
                return TransactionScenario.NORMAL

        # In MIXED mode: 70% NORMAL, 10% HIGH_AMOUNT, 8% NEW_DEVICE, 7% UNUSUAL_LOCATION, 5% HIGH_VELOCITY
        roll = random.random()
        if roll < 0.70:
            return TransactionScenario.NORMAL
        elif roll < 0.80:
            return TransactionScenario.HIGH_AMOUNT
        elif roll < 0.88:
            return TransactionScenario.NEW_DEVICE
        elif roll < 0.95:
            return TransactionScenario.UNUSUAL_LOCATION
        else:
            return TransactionScenario.HIGH_VELOCITY

    async def generate_and_process_transaction(self) -> dict[str, Any]:
        """
        Execute a single transaction cycle:
        1. Select customer and destination from the persistent pool.
        2. Replenish customer balance if depleted.
        3. Generate transaction according to the active scenario.
        4. Calculate behavioral risk features.
        5. Score and persist to PostgreSQL atomically (offloaded to threadpool).
        6. Broadcast events to active WebSocket clients.
        """
        scenario = self._pick_scenario()
        customer = random.choice(self.customers)
        destination = random.choice(self.destinations)

        # Replenish balance if it gets low so the customer can keep transacting
        if customer.account_balance < 10000.0:
            customer.account_balance += 100000.0

        previous_timestamp = None
        if scenario == TransactionScenario.HIGH_VELOCITY and customer.transaction_timestamps:
            previous_timestamp = customer.transaction_timestamps[-1]

        # 1. Generate transaction using existing generator
        transaction = generate_transaction(
            scenario=scenario,
            customer=customer,
            destination=destination,
            previous_timestamp=previous_timestamp,
        )

        # 2. Calculate behavioral features against the customer profile
        behavioral_features = calculate_behavioral_features(
            transaction=transaction,
            customer=customer,
        )

        # 3. Offload ML scoring, atomic database persistence, and WebSocket broadcasting
        result = await process_and_broadcast_transaction(
            transaction,
            behavioral_features,
        )

        # 4. Update simulation metrics upon successful persistence
        self.total_generated += 1
        self.total_successful += 1
        if result.get("fraud_prediction") == 1:
            self.total_fraud += 1

        alerts_created = result.get("alerts", [])
        if alerts_created:
            self.total_alerts += len(alerts_created)
        elif result.get("alert"):
            self.total_alerts += 1

        return result

    async def _stream_loop(self) -> None:
        """Continuous streaming loop executing in the background."""
        logger.info(
            "BankGuard Simulation Stream started (interval=%.2fs, scenario=%s)",
            self.generation_interval,
            self.active_scenario,
        )

        try:
            while self.is_running:
                self._current_step_task = asyncio.create_task(
                    self.generate_and_process_transaction()
                )
                try:
                    await self._current_step_task
                except asyncio.CancelledError:
                    if self._current_step_task and not self._current_step_task.done():
                        # Allow active transaction processing to finish safely
                        await self._current_step_task
                    break
                except Exception as exc:
                    self.total_failed += 1
                    self.last_error = str(exc)
                    logger.exception("Error in simulation stream iteration: %s", exc)
                finally:
                    self._current_step_task = None

                # Check if stop was requested while transaction was in flight
                if not self.is_running:
                    break

                # Wait for next streaming interval
                try:
                    await asyncio.sleep(self.generation_interval)
                except asyncio.CancelledError:
                    break

        except asyncio.CancelledError:
            logger.info("BankGuard Simulation Stream loop cancelled.")
        finally:
            self.is_running = False
            self.stopped_at = datetime.now(timezone.utc)
            self._task = None
            logger.info("BankGuard Simulation Stream loop terminated.")

    def start(
        self,
        generation_interval: float | None = None,
        rate_per_second: float | None = None,
        scenario: str = "MIXED",
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> dict[str, Any]:
        """
        Start the background streaming worker.
        Rejects or safely handles repeated start requests.
        Ensures the background task is successfully created before reporting is_running=True.
        """
        if self.is_running and self._task and not self._task.done():
            return self.get_status()

        # Determine interval: generation_interval takes precedence, then rate_per_second
        if generation_interval is not None and generation_interval > 0:
            interval = max(0.1, min(generation_interval, 60.0))
        elif rate_per_second is not None and rate_per_second > 0:
            interval = max(0.1, min(1.0 / rate_per_second, 60.0))
        else:
            interval = 1.0

        self.generation_interval = interval
        self.active_scenario = scenario.upper() if scenario else "MIXED"

        # Attempt to obtain the running asyncio event loop and schedule the worker task
        try:
            target_loop = loop
            if target_loop is None:
                try:
                    target_loop = asyncio.get_running_loop()
                except RuntimeError:
                    try:
                        target_loop = asyncio.get_event_loop()
                        if target_loop.is_closed():
                            target_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(target_loop)
                    except RuntimeError:
                        target_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(target_loop)

            self._task = target_loop.create_task(self._stream_loop())
            self.is_running = True
            self.started_at = datetime.now(timezone.utc)
            self.stopped_at = None
            self.last_error = None
        except Exception as exc:
            self._task = None
            self.is_running = False
            self.stopped_at = datetime.now(timezone.utc)
            self.last_error = f"Failed to start simulation background worker: {exc}"
            logger.error("Failed to start simulation stream: %s", exc)

        return self.get_status()

    def stop(self) -> dict[str, Any]:
        """
        Stop the background streaming worker safely.
        Signals the loop to stop and prevents new transactions.
        If currently sleeping between intervals, cancels the sleep immediately.
        If an active transaction is processing, it finishes safely before the loop terminates.
        """
        if not self.is_running:
            return self.get_status()

        self.is_running = False
        self.stopped_at = datetime.now(timezone.utc)

        if self._task and not self._task.done():
            # If sleeping (no transaction actively processing), wake up and cancel immediately
            if self._current_step_task is None:
                self._task.cancel()

        if self._current_step_task is None:
            self._task = None

        return self.get_status()

    def get_status(self) -> dict[str, Any]:
        """Return the current streaming engine status and statistics."""
        return {
            "is_running": self.is_running,
            "generation_interval": self.generation_interval,
            "rate_per_second": (
                round(1.0 / self.generation_interval, 2)
                if self.generation_interval > 0
                else 0.0
            ),
            "scenario": self.active_scenario,
            "total_generated": self.total_generated,
            "total_successful": self.total_successful,
            "total_failed": self.total_failed,
            "total_fraud": self.total_fraud,
            "total_alerts": self.total_alerts,
            "connected_clients": ws_manager.connection_count,
            "last_error": self.last_error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
        }


# Global simulation streamer singleton
streamer = SimulationStreamer()
