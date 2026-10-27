import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.transaction import Transaction as TransactionModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["Transactions"],
)


@router.get("")
def get_transactions(
    customer_id: str | None = Query(default=None, min_length=1),
    fraud_prediction: int | None = Query(default=None, ge=0, le=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve stored transactions with optional filters and pagination."""
    try:
        query = select(TransactionModel)

        if customer_id is not None:
            query = query.where(
                TransactionModel.customer_id == customer_id
            )

        if fraud_prediction is not None:
            query = query.where(
                TransactionModel.fraud_prediction == fraud_prediction
            )

        query = (
            query
            .order_by(
                TransactionModel.created_at.desc(),
                TransactionModel.transaction_id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )

        transactions = db.scalars(query).all()

        return {
            "items": [
                {
                    "transaction_id": transaction.transaction_id,
                    "customer_id": transaction.customer_id,
                    "amount": transaction.amount,
                    "merchant_category": transaction.merchant_category,
                    "device_id": transaction.device_id,
                    "location": transaction.location,
                    "timestamp": transaction.timestamp,
                    "payment_method": transaction.payment_method,
                    "transaction_type": transaction.transaction_type,
                    "fraud_prediction": transaction.fraud_prediction,
                    "created_at": transaction.created_at,
                }
                for transaction in transactions
            ],
            "limit": limit,
            "offset": offset,
            "returned": len(transactions),
        }

    except SQLAlchemyError as exc:
        logger.exception("Failed to retrieve transactions")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve transactions.",
        ) from exc