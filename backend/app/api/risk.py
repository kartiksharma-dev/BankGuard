from datetime import datetime, timezone
import logging
from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from backend.app.services.risk_service import (
    broadcast_transaction_events,
    score_submitted_transaction,
)
from backend.app.services.websocket_manager import ws_manager
from simulator.schemas import Transaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/risk", tags=["Risk"])


@router.post("/score")
async def score_transaction_endpoint(transaction: Transaction):
    """
    Score a transaction submitted by an API client.
    Executes ML inference and database persistence, commits changes atomically,
    and broadcasts real-time WebSocket events.
    """
    try:
        result = await run_in_threadpool(score_submitted_transaction, transaction)
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

    # Broadcast WebSocket events on the event loop only after successful database commit
    await broadcast_transaction_events(result, transaction)

    return result
