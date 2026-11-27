from datetime import datetime
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from backend.app.models.alert import Alert
from backend.app.models.investigation import Investigation
from backend.app.schemas.investigation import (
    LEGACY_INVESTIGATION_STATUSES,
    VALID_INVESTIGATION_STATUSES,
    format_timestamped_note,
    merge_investigation_findings,
    normalize_investigation_outcome,
    normalize_investigation_status,
    parse_investigation_findings,
    serialize_investigation_findings,
    validate_assigned_to,
)

logger = logging.getLogger(__name__)

# Sentinel to distinguish omitted arguments from explicit None in partial updates.
UNSET: Any = object()

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"OPEN", "IN_PROGRESS"},
    "IN_PROGRESS": {"IN_PROGRESS", "RESOLVED"},
    "RESOLVED": set(),
    "CLOSED": set(),
}

OUTCOME_TO_ALERT_STATUS: dict[str, str] = {
    "CONFIRMED_FRAUD": "RESOLVED",
    "LEGITIMATE": "DISMISSED",
}


class InvestigationNotFoundError(LookupError):
    """Raised when a requested investigation or linked alert does not exist."""


class InvestigationConflictError(ValueError):
    """Raised when creating a duplicate investigation for an alert."""


class InvestigationValidationError(ValueError):
    """Raised when investigation lifecycle, outcome, or findings validation fails."""


class InvestigationAlertSyncError(RuntimeError):
    """Raised when synchronizing the linked alert fails during investigation resolution."""


def _normalize_optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validate_assignee(value: Any) -> str | None:
    """Validate and normalize analyst assignment using centralized schema rules."""
    try:
        return validate_assigned_to(value)
    except ValueError as exc:
        raise InvestigationValidationError(str(exc)) from exc


def _ensure_mutable(investigation: Investigation) -> None:
    current = (investigation.status or "").strip().upper()
    if current in ("RESOLVED", *LEGACY_INVESTIGATION_STATUSES):
        raise InvestigationValidationError(
            f"Investigation #{investigation.investigation_id} is already '{current}' and cannot be modified."
        )


def _validate_transition(current_status: str, target_status: str) -> str:
    current = (current_status or "").strip().upper()
    target = normalize_investigation_status(target_status)

    allowed_targets = ALLOWED_STATUS_TRANSITIONS.get(current, set())
    if target not in allowed_targets:
        if not allowed_targets:
            raise InvestigationValidationError(
                f"Investigation in terminal status '{current}' cannot transition to '{target}'."
            )
        allowed_str = ", ".join(sorted(allowed_targets))
        raise InvestigationValidationError(
            f"Invalid status transition from '{current}' to '{target}'. "
            f"Allowed transitions: {allowed_str}."
        )
    return target


def _format_note_entry(
    note_text: str,
    *,
    author: str | None = None,
    timestamp: datetime | None = None,
) -> str:
    """Format a timestamped note and translate schema ValueError to InvestigationValidationError."""
    try:
        return format_timestamped_note(note_text, author=author, timestamp=timestamp)
    except ValueError as exc:
        raise InvestigationValidationError(str(exc)) from exc


def _append_to_clean_text(
    existing_clean: str | None,
    note_text: str,
    *,
    author: str | None = None,
    timestamp: datetime | None = None,
) -> str:
    """Append a formatted timestamped note onto clean (header-free) findings text."""
    entry = _format_note_entry(note_text, author=author, timestamp=timestamp)
    return f"{existing_clean}\n{entry}" if existing_clean else entry


def _append_note_body(
    existing_raw_findings: str | None,
    note_text: str,
    *,
    author: str | None = None,
    timestamp: datetime | None = None,
) -> tuple[str | None, str]:
    """
    Append a formatted timestamped note to existing findings text while
    preserving any existing outcome metadata and prior notes.
    Returns (existing_outcome, combined_clean_findings).
    """
    existing_outcome, existing_clean, _ = parse_investigation_findings(existing_raw_findings)
    combined_clean = _append_to_clean_text(
        existing_clean,
        note_text,
        author=author,
        timestamp=timestamp,
    )
    return existing_outcome, combined_clean


def _with_appended_note(
    existing_raw_findings: str | None,
    note_text: str,
    *,
    author: str | None = None,
    timestamp: datetime | None = None,
) -> str | None:
    """Return raw serialized findings with a new timestamped note appended cleanly."""
    existing_outcome, combined_clean = _append_note_body(
        existing_raw_findings,
        note_text,
        author=author,
        timestamp=timestamp,
    )
    return serialize_investigation_findings(
        outcome=existing_outcome,
        findings_text=combined_clean,
    )


def _apply_appended_note(
    investigation: Investigation,
    note_text: str,
    *,
    author: str | None = None,
    timestamp: datetime | None = None,
) -> None:
    """Append a timestamped note to an investigation while preserving outcome and prior notes."""
    investigation.findings = _with_appended_note(
        investigation.findings,
        note_text,
        author=author,
        timestamp=timestamp,
    )


def _sync_alert_status(
    db: Session,
    investigation: Investigation,
    outcome: str,
) -> None:
    """Synchronize the linked alert status atomically inside the active transaction."""
    alert = investigation.alert or db.get(Alert, investigation.alert_id)
    if alert is None:
        raise InvestigationNotFoundError(
            f"Linked alert #{investigation.alert_id} not found for investigation #{investigation.investigation_id}."
        )
    alert.status = OUTCOME_TO_ALERT_STATUS[outcome]
    db.flush()


def _commit_and_refresh(
    db: Session,
    investigation: Investigation,
    *,
    conflict_detail: str | None = None,
    reload_context: bool = False,
) -> Investigation:
    try:
        db.commit()
        if reload_context:
            return get_investigation_by_id(
                db,
                investigation.investigation_id,
                include_context=True,
            )
        db.refresh(investigation)
        return investigation
    except IntegrityError as exc:
        db.rollback()
        if conflict_detail:
            raise InvestigationConflictError(conflict_detail) from exc
        raise
    except SQLAlchemyError:
        db.rollback()
        raise


def _apply_mutations_and_commit(
    db: Session,
    investigation: Investigation,
    *,
    new_status: str,
    new_findings: str | None,
    new_assignee: Any = UNSET,
    sync_outcome: str | None = None,
    reload_context: bool = False,
) -> Investigation:
    """
    Apply validated mutations to investigation and linked alert atomically.
    Rolls back the active transaction on any sync or persistence error.
    """
    try:
        if new_assignee is not UNSET:
            investigation.assigned_to = new_assignee
        investigation.status = new_status
        investigation.findings = new_findings

        if sync_outcome is not None:
            try:
                _sync_alert_status(db, investigation, sync_outcome)
            except (InvestigationNotFoundError, InvestigationValidationError):
                raise
            except Exception as exc:
                raise InvestigationAlertSyncError(
                    f"Failed to synchronize linked alert #{investigation.alert_id}: {exc}"
                ) from exc

        return _commit_and_refresh(
            db,
            investigation,
            reload_context=reload_context,
        )
    except Exception:
        db.rollback()
        raise


def get_investigation_by_id(
    db: Session,
    investigation_id: int,
    *,
    include_context: bool = False,
) -> Investigation:
    """Retrieve one investigation by ID, optionally eager-loading linked alert and transaction."""
    if include_context:
        query = (
            select(Investigation)
            .options(joinedload(Investigation.alert).joinedload(Alert.transaction))
            .execution_options(populate_existing=True)
            .where(Investigation.investigation_id == investigation_id)
        )
        investigation = db.scalar(query)
    else:
        investigation = db.get(Investigation, investigation_id)

    if investigation is None:
        raise InvestigationNotFoundError("Investigation not found.")

    return investigation


def list_investigations(
    db: Session,
    *,
    alert_id: int | None = None,
    status: str | None = None,
    assigned_to: str | None = None,
    outcome: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_context: bool = False,
) -> list[Investigation]:
    """List investigations with optional filtering, pagination, and optional context."""
    query = select(Investigation)

    if include_context:
        query = query.options(
            joinedload(Investigation.alert).joinedload(Alert.transaction)
        ).execution_options(populate_existing=True)

    if alert_id is not None:
        query = query.where(Investigation.alert_id == alert_id)

    if status is not None:
        normalized_status = status.strip().upper()
        allowed_read_statuses = (*VALID_INVESTIGATION_STATUSES, *LEGACY_INVESTIGATION_STATUSES)
        if normalized_status not in allowed_read_statuses:
            allowed_str = ", ".join(VALID_INVESTIGATION_STATUSES)
            raise InvestigationValidationError(
                f"Invalid investigation status '{status}'. Allowed values: {allowed_str}."
            )
        query = query.where(Investigation.status == normalized_status)

    if assigned_to is not None:
        query = query.where(Investigation.assigned_to == assigned_to)

    if outcome is not None:
        try:
            normalized_outcome = normalize_investigation_outcome(outcome)
        except ValueError as exc:
            raise InvestigationValidationError(str(exc)) from exc
        query = query.where(
            Investigation.findings.like(f"[OUTCOME: {normalized_outcome}]%")
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


def create_investigation(
    db: Session,
    *,
    alert_id: int,
    assigned_to: str | None = None,
    initial_note: str | None = None,
) -> Investigation:
    """Create a new OPEN investigation linked to an existing alert."""
    clean_assignee = _validate_assignee(assigned_to)

    alert = db.get(Alert, alert_id)
    if alert is None:
        raise InvestigationNotFoundError("Alert not found.")

    existing = db.scalar(
        select(Investigation).where(Investigation.alert_id == alert_id)
    )
    if existing is not None:
        raise InvestigationConflictError("An investigation already exists for this alert.")

    clean_note = _normalize_optional_str(initial_note)
    findings_value = (
        _format_note_entry(clean_note, author=clean_assignee)
        if clean_note
        else None
    )

    investigation = Investigation(
        alert_id=alert_id,
        assigned_to=clean_assignee,
        status="OPEN",
        findings=findings_value,
    )
    db.add(investigation)

    return _commit_and_refresh(
        db,
        investigation,
        conflict_detail="Unable to create the investigation because of a database conflict.",
    )


def assign_investigation(
    db: Session,
    investigation_id: int,
    *,
    assigned_to: str | None,
    note: str | None = None,
    author: str | None = None,
) -> Investigation:
    """Assign, reassign, or explicitly unassign (None) an analyst on a mutable investigation."""
    clean_assignee = _validate_assignee(assigned_to)

    investigation = get_investigation_by_id(db, investigation_id)
    _ensure_mutable(investigation)

    investigation.assigned_to = clean_assignee

    clean_note = _normalize_optional_str(note)
    if clean_note:
        _apply_appended_note(
            investigation,
            clean_note,
            author=_normalize_optional_str(author) or clean_assignee,
        )

    return _commit_and_refresh(db, investigation)


def start_investigation(
    db: Session,
    investigation_id: int,
    *,
    assigned_to: Any = UNSET,
    note: str | None = None,
) -> Investigation:
    """Transition an OPEN investigation to IN_PROGRESS while preserving existing assignment if omitted."""
    validated_assignee: Any = UNSET
    if assigned_to is not UNSET:
        validated_assignee = _validate_assignee(assigned_to)

    investigation = get_investigation_by_id(db, investigation_id)
    current_status = (investigation.status or "").strip().upper()
    if current_status != "OPEN":
        raise InvestigationValidationError(
            f"Only OPEN investigations can be started (current status: '{current_status}')."
        )

    target_status = _validate_transition(current_status, "IN_PROGRESS")
    effective_assignee = (
        validated_assignee if validated_assignee is not UNSET else investigation.assigned_to
    )

    next_findings = investigation.findings
    clean_note = _normalize_optional_str(note)
    if clean_note:
        next_findings = _with_appended_note(
            next_findings,
            clean_note,
            author=effective_assignee,
        )

    return _apply_mutations_and_commit(
        db,
        investigation,
        new_status=target_status,
        new_findings=next_findings,
        new_assignee=validated_assignee,
    )


def add_investigation_note(
    db: Session,
    investigation_id: int,
    *,
    note: str,
    author: str | None = None,
    timestamp: datetime | None = None,
) -> Investigation:
    """Append a timestamped note without overwriting prior investigation findings."""
    investigation = get_investigation_by_id(db, investigation_id)
    _ensure_mutable(investigation)

    clean_note = _normalize_optional_str(note)
    if not clean_note:
        raise InvestigationValidationError("Investigation note cannot be empty.")

    effective_author = _normalize_optional_str(author) or investigation.assigned_to
    _apply_appended_note(
        investigation,
        clean_note,
        author=effective_author,
        timestamp=timestamp,
    )

    return _commit_and_refresh(db, investigation)


def resolve_investigation(
    db: Session,
    investigation_id: int,
    *,
    outcome: str,
    findings: str | None = None,
    assigned_to: Any = UNSET,
    author: str | None = None,
    timestamp: datetime | None = None,
) -> Investigation:
    """
    Resolve an IN_PROGRESS investigation with a mandatory final outcome
    (CONFIRMED_FRAUD or LEGITIMATE) and non-empty findings, atomically
    synchronizing the linked alert status.
    """
    validated_assignee: Any = UNSET
    if assigned_to is not UNSET:
        validated_assignee = _validate_assignee(assigned_to)

    try:
        normalized_outcome = normalize_investigation_outcome(outcome)
    except ValueError as exc:
        raise InvestigationValidationError(str(exc)) from exc

    investigation = get_investigation_by_id(db, investigation_id, include_context=True)
    target_status = _validate_transition(investigation.status, "RESOLVED")

    effective_assignee = (
        validated_assignee if validated_assignee is not UNSET else investigation.assigned_to
    )

    _, existing_clean, _ = parse_investigation_findings(investigation.findings)
    new_findings = _normalize_optional_str(findings)

    if new_findings is not None:
        effective_author = _normalize_optional_str(author) or effective_assignee
        combined_clean = _append_to_clean_text(
            existing_clean,
            new_findings,
            author=effective_author,
            timestamp=timestamp,
        )
    else:
        combined_clean = existing_clean

    if not combined_clean:
        raise InvestigationValidationError(
            "Investigation findings are required to resolve an investigation."
        )

    serialized_findings = serialize_investigation_findings(
        outcome=normalized_outcome,
        findings_text=combined_clean,
    )

    return _apply_mutations_and_commit(
        db,
        investigation,
        new_status=target_status,
        new_findings=serialized_findings,
        new_assignee=validated_assignee,
        sync_outcome=normalized_outcome,
        reload_context=True,
    )


def update_investigation(
    db: Session,
    investigation_id: int,
    *,
    assigned_to: Any = UNSET,
    status: Any = UNSET,
    findings: Any = UNSET,
    note: Any = UNSET,
    outcome: Any = UNSET,
    append_findings: bool = False,
) -> Investigation:
    """
    Update investigation fields while enforcing lifecycle rules, outcome
    constraints, historical findings/note preservation, and atomic alert synchronization.
    """
    provided = [assigned_to, status, findings, note, outcome]
    if all(arg is UNSET for arg in provided):
        raise InvestigationValidationError(
            "At least one field must be provided for an update."
        )

    validated_assignee: Any = UNSET
    if assigned_to is not UNSET:
        validated_assignee = _validate_assignee(assigned_to)

    investigation = get_investigation_by_id(db, investigation_id, include_context=True)
    _ensure_mutable(investigation)

    current_status = (investigation.status or "").strip().upper()
    target_status = current_status
    if status is not UNSET and status is not None:
        try:
            target_status = _validate_transition(current_status, str(status))
        except ValueError as exc:
            raise InvestigationValidationError(str(exc)) from exc
    elif status is None:
        raise InvestigationValidationError("Status cannot be null.")

    normalized_outcome: str | None = None
    if outcome is not UNSET and outcome is not None:
        try:
            normalized_outcome = normalize_investigation_outcome(str(outcome))
        except ValueError as exc:
            raise InvestigationValidationError(str(exc)) from exc

    if normalized_outcome is not None and target_status != "RESOLVED":
        raise InvestigationValidationError(
            "Final outcome can only be recorded when resolving an investigation (status='RESOLVED')."
        )

    if target_status == "RESOLVED" and normalized_outcome is None:
        raise InvestigationValidationError(
            "A valid final outcome ('CONFIRMED_FRAUD' or 'LEGITIMATE') is required when resolving an investigation."
        )

    effective_assignee = (
        validated_assignee if validated_assignee is not UNSET else investigation.assigned_to
    )
    existing_outcome, _, _ = parse_investigation_findings(investigation.findings)
    next_raw_findings = investigation.findings

    if findings is not UNSET:
        if append_findings and isinstance(findings, str) and findings.strip():
            next_raw_findings = _with_appended_note(
                next_raw_findings,
                findings.strip(),
                author=effective_assignee,
            )
        else:
            next_raw_findings = merge_investigation_findings(
                next_raw_findings,
                new_findings=findings,
                outcome_override=existing_outcome,
            )

    if note is not UNSET and note is not None:
        clean_note = _normalize_optional_str(str(note))
        if not clean_note:
            raise InvestigationValidationError("Investigation note cannot be empty.")
        next_raw_findings = _with_appended_note(
            next_raw_findings,
            clean_note,
            author=effective_assignee,
        )

    _, next_clean_findings, _ = parse_investigation_findings(next_raw_findings)

    if target_status == "RESOLVED" and not next_clean_findings:
        raise InvestigationValidationError(
            "Investigation findings are required to resolve an investigation."
        )

    final_outcome = normalized_outcome if target_status == "RESOLVED" else existing_outcome
    serialized_findings = serialize_investigation_findings(
        outcome=final_outcome,
        findings_text=next_clean_findings,
    )

    return _apply_mutations_and_commit(
        db,
        investigation,
        new_status=target_status,
        new_findings=serialized_findings,
        new_assignee=validated_assignee,
        sync_outcome=normalized_outcome if target_status == "RESOLVED" else None,
        reload_context=True,
    )
