import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, distinct, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.alert import Alert
from backend.app.models.investigation import Investigation
from backend.app.models.transaction import Transaction

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard"],
)


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Retrieve aggregated dashboard statistics.
    
    Metrics:
    - total_transactions: Total count of persisted transactions
    - fraud_detected: Count of transactions with fraud_prediction == 1
    - high_risk_transactions: Transactions flagged as fraud or linked to alerts
    - open_alerts: Count of alerts with status == 'OPEN'
    - investigations_in_progress: Count of investigations with status == 'IN_PROGRESS'
    - fraud_rate: Percentage of total transactions predicted as fraud (0.0 if empty)
    """
    try:
        total_tx = db.scalar(select(func.count(Transaction.transaction_id))) or 0
        fraud_tx = (
            db.scalar(
                select(func.count(Transaction.transaction_id)).where(
                    Transaction.fraud_prediction == 1
                )
            )
            or 0
        )

        # High-risk transactions include those flagged as fraud by the model OR linked to an alert
        high_risk_query = (
            select(func.count(distinct(Transaction.transaction_id)))
            .outerjoin(Alert, Transaction.transaction_id == Alert.transaction_id)
            .where(
                (Transaction.fraud_prediction == 1) | (Alert.alert_id.isnot(None))
            )
        )
        high_risk_tx = db.scalar(high_risk_query) or 0

        open_alerts = (
            db.scalar(
                select(func.count(Alert.alert_id)).where(
                    func.upper(Alert.status) == "OPEN"
                )
            )
            or 0
        )

        in_progress_investigations = (
            db.scalar(
                select(func.count(Investigation.investigation_id)).where(
                    func.upper(Investigation.status) == "IN_PROGRESS"
                )
            )
            or 0
        )

        fraud_rate = (
            round((fraud_tx / total_tx) * 100, 2) if total_tx > 0 else 0.0
        )

        return {
            "total_transactions": total_tx,
            "fraud_detected": fraud_tx,
            "high_risk_transactions": high_risk_tx,
            "open_alerts": open_alerts,
            "investigations_in_progress": in_progress_investigations,
            "fraud_rate": fraud_rate,
        }

    except SQLAlchemyError as exc:
        logger.exception("Failed to retrieve dashboard stats")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve dashboard statistics.",
        ) from exc


@router.get("/charts")
def get_dashboard_charts(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Retrieve real aggregated chart datasets for the dashboard.
    
    Includes:
    - volume_by_date: Transaction count & fraud count grouped by date
    - category_distribution: Transaction breakdown by merchant_category
    - location_distribution: Transaction breakdown by location (top 10)
    - risk_distribution: Low risk vs high risk breakdown
    """
    try:
        # 1. Volume by date (using cast to date)
        date_trunc = func.date(Transaction.timestamp)
        date_query = (
            select(
                date_trunc.label("tx_date"),
                func.count(Transaction.transaction_id).label("total"),
                func.sum(
                    case((Transaction.fraud_prediction == 1, 1), else_=0)
                ).label("fraud"),
            )
            .group_by(date_trunc)
            .order_by(date_trunc.asc())
            .limit(30)
        )
        date_rows = db.execute(date_query).all()
        volume_by_date = [
            {
                "date": str(row.tx_date),
                "total": int(row.total or 0),
                "fraud": int(row.fraud or 0),
            }
            for row in date_rows
        ]

        # 2. Category distribution
        cat_query = (
            select(
                Transaction.merchant_category,
                func.count(Transaction.transaction_id).label("total"),
                func.sum(
                    case((Transaction.fraud_prediction == 1, 1), else_=0)
                ).label("fraud"),
            )
            .group_by(Transaction.merchant_category)
            .order_by(func.count(Transaction.transaction_id).desc())
            .limit(10)
        )
        cat_rows = db.execute(cat_query).all()
        category_distribution = [
            {
                "category": str(row.merchant_category),
                "total": int(row.total or 0),
                "fraud": int(row.fraud or 0),
            }
            for row in cat_rows
        ]

        # 3. Location distribution
        loc_query = (
            select(
                Transaction.location,
                func.count(Transaction.transaction_id).label("total"),
                func.sum(
                    case((Transaction.fraud_prediction == 1, 1), else_=0)
                ).label("fraud"),
            )
            .group_by(Transaction.location)
            .order_by(func.count(Transaction.transaction_id).desc())
            .limit(10)
        )
        loc_rows = db.execute(loc_query).all()
        location_distribution = [
            {
                "location": str(row.location),
                "total": int(row.total or 0),
                "fraud": int(row.fraud or 0),
            }
            for row in loc_rows
        ]

        # 4. Risk distribution (consistent with high_risk_transactions metric)
        total_tx = db.scalar(select(func.count(Transaction.transaction_id))) or 0
        high_risk_query = (
            select(func.count(distinct(Transaction.transaction_id)))
            .outerjoin(Alert, Transaction.transaction_id == Alert.transaction_id)
            .where(
                (Transaction.fraud_prediction == 1) | (Alert.alert_id.isnot(None))
            )
        )
        high_risk_tx = db.scalar(high_risk_query) or 0
        low_risk_tx = max(0, total_tx - high_risk_tx)

        risk_distribution = [
            {"name": "Low Risk", "value": low_risk_tx, "color": "#10B981"},
            {"name": "High Risk / Flagged", "value": high_risk_tx, "color": "#EF4444"},
        ]

        return {
            "volume_by_date": volume_by_date,
            "category_distribution": category_distribution,
            "location_distribution": location_distribution,
            "risk_distribution": risk_distribution,
        }

    except SQLAlchemyError as exc:
        logger.exception("Failed to retrieve dashboard charts")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve dashboard chart data.",
        ) from exc
    