import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.alert import Alert
from backend.app.models.investigation import Investigation
from backend.app.schemas.investigation import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/investigations",
    tags=["Investigations"],
)


@router.post(
    "",
    response_model=InvestigationResponse,
    status_code=201,
)
def create_investigation(
    payload: InvestigationCreate,
    db: Session = Depends(get_db),
):
    """Create an investigation for an existing alert."""
    alert = db.get(Alert, payload.alert_id)

    if alert is None:
        raise HTTPException(
            status_code=404,
            detail="Alert not found.",
        )

    existing_investigation = db.scalar(
        select(Investigation).where(
            Investigation.alert_id == payload.alert_id
        )
    )

    if existing_investigation is not None:
        raise HTTPException(
            status_code=409,
            detail="An investigation already exists for this alert.",
        )

    investigation = Investigation(
        alert_id=payload.alert_id,
        assigned_to=payload.assigned_to,
    )

    try:
        db.add(investigation)
        db.commit()
        db.refresh(investigation)
        return investigation

    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "Investigation creation conflicted for alert_id=%s",
            payload.alert_id,
        )
        raise HTTPException(
            status_code=409,
            detail="Unable to create the investigation because of a database conflict.",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while creating investigation")
        raise HTTPException(
            status_code=500,
            detail="Unable to create investigation.",
        ) from exc


@router.get(
    "",
    response_model=list[InvestigationResponse],
)
def get_investigations(
    alert_id: int | None = Query(default=None, gt=0),
    status: str | None = Query(
        default=None,
        min_length=1,
        max_length=30,
    ),
    assigned_to: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve investigations with optional filters and pagination."""
    try:
        query = select(Investigation)

        if alert_id is not None:
            query = query.where(
                Investigation.alert_id == alert_id
            )

        if status is not None:
            query = query.where(
                Investigation.status == status.upper()
            )

        if assigned_to is not None:
            query = query.where(
                Investigation.assigned_to == assigned_to
            )

        query = (
            query
            .order_by(
                Investigation.created_at.desc(),
                Investigation.investigation_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return list(db.scalars(query).all())

    except SQLAlchemyError as exc:
        logger.exception("Failed to retrieve investigations")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve investigations.",
        ) from exc


@router.get(
    "/{investigation_id}",
    response_model=InvestigationResponse,
)
def get_investigation(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve one investigation by its ID."""
    investigation = db.get(Investigation, investigation_id)

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found.",
        )

    return investigation


@router.patch(
    "/{investigation_id}",
    response_model=InvestigationResponse,
)
def update_investigation(
    investigation_id: int,
    payload: InvestigationUpdate,
    db: Session = Depends(get_db),
):
    """Update an investigation's assignee, status, or findings."""
    investigation = db.get(Investigation, investigation_id)

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found.",
        )

    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=422,
            detail="At least one field must be provided for an update.",
        )

    if "status" in updates and updates["status"] is not None:
        updates["status"] = updates["status"].strip().upper()

        if not updates["status"]:
            raise HTTPException(
                status_code=422,
                detail="Status cannot be empty.",
            )

    if "assigned_to" in updates and updates["assigned_to"] is not None:
        updates["assigned_to"] = updates["assigned_to"].strip() or None

    try:
        for field, value in updates.items():
            setattr(investigation, field, value)

        db.commit()
        db.refresh(investigation)
        return investigation

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception(
            "Database error while updating investigation_id=%s",
            investigation_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to update investigation.",
        ) from exc