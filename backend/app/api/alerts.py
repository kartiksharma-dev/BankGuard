import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.alert import Alert
from backend.app.models.transaction import Transaction
from backend.app.schemas.alert import AlertCreate, AlertResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/alerts",
    tags=["Alerts"],
)


@router.post("", response_model=AlertResponse, status_code=201)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
):
    """Create an alert for an existing transaction."""

    transaction = db.get(Transaction, payload.transaction_id)

    if transaction is None:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found.",
        )

    alert = Alert(
        transaction_id=payload.transaction_id,
        alert_type=payload.alert_type,
    )

    try:
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    except IntegrityError as exc:
        db.rollback()
        logger.exception("Database integrity error while creating alert")
        raise HTTPException(
            status_code=409,
            detail="Unable to create the alert because of a database conflict.",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while creating alert")
        raise HTTPException(
            status_code=500,
            detail="Unable to create alert.",
        ) from exc


@router.get("", response_model=list[AlertResponse])
def get_alerts(
    transaction_id: str | None = Query(default=None, min_length=1),
    status: str | None = Query(default=None, min_length=1, max_length=30),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve alerts with optional filters and pagination."""

    try:
        query = select(Alert)

        if transaction_id is not None:
            query = query.where(Alert.transaction_id == transaction_id)

        if status is not None:
            query = query.where(Alert.status == status.upper())

        query = (
            query
            .order_by(Alert.created_at.desc(), Alert.alert_id.desc())
            .offset(offset)
            .limit(limit)
        )

        return list(db.scalars(query).all())

    except SQLAlchemyError as exc:
        logger.exception("Failed to retrieve alerts")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve alerts.",
        ) from exc


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve one alert by its ID."""

    alert = db.get(Alert, alert_id)

    if alert is None:
        raise HTTPException(
            status_code=404,
            detail="Alert not found.",
        )

    return alert