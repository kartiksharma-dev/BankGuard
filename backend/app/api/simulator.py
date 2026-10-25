import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.services.risk_decision_engine import (
    assess_transaction_risk,
)
from simulator.pipeline import score_transaction
from simulator.scenarios import TransactionScenario

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/simulator",
    tags=["Simulator"],
)


class SimulationRequest(BaseModel):
    scenario: TransactionScenario = TransactionScenario.NORMAL


@router.post("/transactions")
def simulate_transaction(request: SimulationRequest):
    """Generate a transaction and return its risk assessment."""

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
