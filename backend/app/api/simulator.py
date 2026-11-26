from datetime import datetime
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from backend.app.services.risk_decision_engine import (
    assess_transaction_risk,
)
from backend.app.services.simulator_service import streamer
from simulator.pipeline import score_transaction
from simulator.scenarios import TransactionScenario

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/simulator",
    tags=["Simulator"],
)


class SimulationRequest(BaseModel):
    scenario: TransactionScenario = TransactionScenario.NORMAL


class StreamStartRequest(BaseModel):
    generation_interval: float | None = Field(default=None, gt=0.0, le=60.0)
    interval_seconds: float | None = Field(default=None, gt=0.0, le=60.0)
    rate_per_second: float | None = Field(default=None, gt=0.0, le=10.0)
    scenario: str = Field(default="MIXED", max_length=50)

    @model_validator(mode="after")
    def resolve_interval(self) -> "StreamStartRequest":
        # Resolve interval with precedence: generation_interval -> interval_seconds -> 1.0 / rate_per_second
        if self.generation_interval is not None:
            pass
        elif self.interval_seconds is not None:
            self.generation_interval = self.interval_seconds
        elif self.rate_per_second is not None:
            self.generation_interval = round(1.0 / self.rate_per_second, 3)
        else:
            self.generation_interval = 1.0
        return self


class StreamStatusResponse(BaseModel):
    is_running: bool
    generation_interval: float
    rate_per_second: float = 0.0
    scenario: str
    total_generated: int
    total_successful: int
    total_failed: int
    total_fraud: int
    total_alerts: int
    connected_clients: int = 0
    last_error: str | None = None
    started_at: datetime | str | None = None
    stopped_at: datetime | str | None = None


@router.post("/transactions")
def simulate_transaction(request: SimulationRequest):
    """Generate a single in-memory transaction and return its risk assessment."""

    try:
        result = score_transaction(scenario=request.scenario)

        transaction = result["transaction"]
        fraud_prediction = result["fraud_prediction"]
        behavioral_features = result["behavioral_features"]

        risk_assessment = assess_transaction_risk(
            fraud_prediction=fraud_prediction,
            behavioral_features=behavioral_features,
        )

        return {
            "transaction": transaction.model_dump(mode="json"),
            "fraud_prediction": fraud_prediction,
            "behavioral_features": behavioral_features,
            "risk_assessment": risk_assessment,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="A required ML artifact could not be found.",
        ) from exc

    except Exception as exc:
        logger.exception("Transaction simulation failed")
        raise HTTPException(
            status_code=500,
            detail="Transaction simulation failed.",
        ) from exc


@router.post("/stream/start", response_model=StreamStatusResponse)
async def start_simulation_stream(request: StreamStartRequest | None = None):
    """Start the background streaming simulation engine."""
    interval = request.generation_interval if request else 1.0
    scenario = request.scenario if request else "MIXED"
    return streamer.start(generation_interval=interval, scenario=scenario)


@router.post("/stream/stop", response_model=StreamStatusResponse)
async def stop_simulation_stream():
    """Stop the background streaming simulation engine safely."""
    return streamer.stop()


@router.get("/stream/status", response_model=StreamStatusResponse)
async def get_simulation_stream_status():
    """Retrieve real-time metrics and operational status of the streaming engine."""
    return streamer.get_status()
