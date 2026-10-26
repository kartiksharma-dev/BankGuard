from fastapi import APIRouter, HTTPException
import logging

from backend.app.services.risk_service import score_submitted_transaction
from simulator.schemas import Transaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix ="/api/v1/risk",tags=["Risk"])

@router.post("/score")
def score_transaction_endpoint(transaction: Transaction):
    """Score a transaction submitted by an API client."""
    try:
        return score_submitted_transaction(transaction)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="A required ML artifact could not be found.",
        ) from exc
    except Exception as exc:
        logger.exception("Transaction scoring failed")
        raise HTTPException(
            status_code=500,
            detail="Transaction scoring failed.",
        ) from exc