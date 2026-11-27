from collections.abc import Callable
import logging
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.investigation import (
    InvestigationAssignRequest,
    InvestigationCreate,
    InvestigationNoteCreate,
    InvestigationResolveRequest,
    InvestigationResponse,
    InvestigationStartRequest,
    InvestigationUpdate,
)
from backend.app.services import investigation_service
from backend.app.services.investigation_service import (
    InvestigationAlertSyncError,
    InvestigationConflictError,
    InvestigationNotFoundError,
    InvestigationValidationError,
    UNSET,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/investigations",
    tags=["Investigations"],
)

_T = TypeVar("_T")


def _optional_field(payload: BaseModel, field_name: str) -> Any:
    """Return an explicitly supplied field value or UNSET when omitted by the client."""
    if field_name in payload.model_fields_set:
        return getattr(payload, field_name)
    return UNSET


def _execute_service_call(
    db: Session,
    action: Callable[[], _T],
    *,
    fallback_error_detail: str,
) -> _T:
    """Execute an investigation service call and translate domain/DB errors to HTTP responses."""
    try:
        return action()
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvestigationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvestigationValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvestigationAlertSyncError as exc:
        logger.exception("Investigation alert synchronization failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to resolve investigation because alert synchronization failed.",
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Database conflict while processing investigation request")
        raise HTTPException(
            status_code=409,
            detail="Unable to save investigation because of a database conflict.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception(fallback_error_detail)
        raise HTTPException(
            status_code=500,
            detail=fallback_error_detail,
        ) from exc


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
    return _execute_service_call(
        db,
        lambda: investigation_service.create_investigation(
            db,
            alert_id=payload.alert_id,
            assigned_to=payload.assigned_to,
            initial_note=payload.initial_note,
        ),
        fallback_error_detail="Unable to create investigation.",
    )


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
    outcome: str | None = Query(
        default=None,
        min_length=1,
        max_length=30,
    ),
    include_context: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve investigations with optional filters, pagination, and optional context."""
    return _execute_service_call(
        db,
        lambda: investigation_service.list_investigations(
            db,
            alert_id=alert_id,
            status=status,
            assigned_to=assigned_to,
            outcome=outcome,
            limit=limit,
            offset=offset,
            include_context=include_context,
        ),
        fallback_error_detail="Unable to retrieve investigations.",
    )


@router.get(
    "/{investigation_id}",
    response_model=InvestigationResponse,
)
def get_investigation(
    investigation_id: int,
    include_context: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Retrieve one investigation by its ID."""
    return _execute_service_call(
        db,
        lambda: investigation_service.get_investigation_by_id(
            db,
            investigation_id,
            include_context=include_context,
        ),
        fallback_error_detail="Unable to retrieve investigation.",
    )


@router.post(
    "/{investigation_id}/assign",
    response_model=InvestigationResponse,
)
def assign_investigation(
    investigation_id: int,
    payload: InvestigationAssignRequest,
    db: Session = Depends(get_db),
):
    """Assign, reassign, or explicitly unassign (null) an analyst on an investigation."""
    return _execute_service_call(
        db,
        lambda: investigation_service.assign_investigation(
            db,
            investigation_id,
            assigned_to=payload.assigned_to,
            note=payload.note,
            author=payload.author,
        ),
        fallback_error_detail="Unable to assign investigation.",
    )


@router.post(
    "/{investigation_id}/start",
    response_model=InvestigationResponse,
)
def start_investigation(
    investigation_id: int,
    payload: InvestigationStartRequest | None = None,
    db: Session = Depends(get_db),
):
    """Transition an OPEN investigation to IN_PROGRESS."""
    assigned_to = (
        _optional_field(payload, "assigned_to") if payload is not None else UNSET
    )
    note = payload.note if payload is not None else None
    return _execute_service_call(
        db,
        lambda: investigation_service.start_investigation(
            db,
            investigation_id,
            assigned_to=assigned_to,
            note=note,
        ),
        fallback_error_detail="Unable to start investigation.",
    )


@router.post(
    "/{investigation_id}/notes",
    response_model=InvestigationResponse,
)
def add_investigation_note(
    investigation_id: int,
    payload: InvestigationNoteCreate,
    db: Session = Depends(get_db),
):
    """Append a timestamped note to an active investigation."""
    return _execute_service_call(
        db,
        lambda: investigation_service.add_investigation_note(
            db,
            investigation_id,
            note=payload.note,
            author=payload.author,
        ),
        fallback_error_detail="Unable to add investigation note.",
    )


@router.post(
    "/{investigation_id}/resolve",
    response_model=InvestigationResponse,
)
def resolve_investigation(
    investigation_id: int,
    payload: InvestigationResolveRequest,
    db: Session = Depends(get_db),
):
    """Resolve an IN_PROGRESS investigation with a final outcome and sync the linked alert."""
    return _execute_service_call(
        db,
        lambda: investigation_service.resolve_investigation(
            db,
            investigation_id,
            outcome=payload.outcome,
            findings=payload.findings,
            assigned_to=_optional_field(payload, "assigned_to"),
            author=payload.author,
        ),
        fallback_error_detail="Unable to resolve investigation.",
    )


@router.patch(
    "/{investigation_id}",
    response_model=InvestigationResponse,
)
def update_investigation(
    investigation_id: int,
    payload: InvestigationUpdate,
    db: Session = Depends(get_db),
):
    """Partially update an investigation's assignee, status, findings, notes, or outcome."""
    return _execute_service_call(
        db,
        lambda: investigation_service.update_investigation(
            db,
            investigation_id,
            assigned_to=_optional_field(payload, "assigned_to"),
            status=_optional_field(payload, "status"),
            findings=_optional_field(payload, "findings"),
            note=_optional_field(payload, "note"),
            outcome=_optional_field(payload, "outcome"),
        ),
        fallback_error_detail="Unable to update investigation.",
    )
