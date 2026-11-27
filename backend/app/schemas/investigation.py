from datetime import datetime, timezone
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import inspect as sa_inspect


InvestigationStatus = Literal["OPEN", "IN_PROGRESS", "RESOLVED"]
InvestigationOutcome = Literal["CONFIRMED_FRAUD", "LEGITIMATE"]

VALID_INVESTIGATION_STATUSES: tuple[str, ...] = ("OPEN", "IN_PROGRESS", "RESOLVED")
LEGACY_INVESTIGATION_STATUSES: tuple[str, ...] = ("CLOSED",)
VALID_INVESTIGATION_OUTCOMES: tuple[str, ...] = ("CONFIRMED_FRAUD", "LEGITIMATE")
MAX_ASSIGNED_TO_LENGTH: int = 100

_OUTCOME_PREFIX_TEMPLATE = "[OUTCOME: {outcome}]"
_OUTCOME_HEADER_RE = re.compile(
    r"^\[OUTCOME:\s*(CONFIRMED_FRAUD|LEGITIMATE)\]\s*(?:\r?\n)?",
)
_TIMESTAMPED_NOTE_RE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))\]\s+(?:\[by:\s*([^\]]+)\]\s+)?(.*)$"
)


class InvestigationNote(BaseModel):
    """Structured representation of a single note inside investigation findings."""

    timestamp: str | None = None
    author: str | None = None
    content: str


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def validate_assigned_to(value: Any) -> str | None:
    """
    Validate and normalize an analyst assignment value.

    - None is permitted (unassigned / explicit unassignment).
    - Whitespace-only strings are rejected.
    - Strings exceeding MAX_ASSIGNED_TO_LENGTH (100) characters are rejected.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Assigned analyst must be a string.")
    stripped = value.strip()
    if not stripped:
        raise ValueError("Assigned analyst cannot be empty or whitespace-only.")
    if len(stripped) > MAX_ASSIGNED_TO_LENGTH:
        raise ValueError(
            f"Assigned analyst must not exceed {MAX_ASSIGNED_TO_LENGTH} characters."
        )
    return stripped


def normalize_investigation_status(value: str) -> str:
    """Normalize and validate an investigation status value."""
    normalized = value.strip().upper()
    if normalized not in VALID_INVESTIGATION_STATUSES:
        allowed = ", ".join(VALID_INVESTIGATION_STATUSES)
        raise ValueError(f"Invalid investigation status '{value}'. Allowed values: {allowed}.")
    return normalized


def normalize_investigation_outcome(value: str) -> str:
    """Normalize and validate a final investigation outcome."""
    normalized = value.strip().upper()
    if normalized not in VALID_INVESTIGATION_OUTCOMES:
        allowed = ", ".join(VALID_INVESTIGATION_OUTCOMES)
        raise ValueError(f"Invalid investigation outcome '{value}'. Allowed values: {allowed}.")
    return normalized


def parse_investigation_findings(
    raw_findings: str | None,
) -> tuple[str | None, str | None, list[InvestigationNote]]:
    """
    Parse raw persisted Investigation.findings text into:
    - extracted outcome ('CONFIRMED_FRAUD' | 'LEGITIMATE' | None)
    - clean human-readable findings text (without internal outcome header)
    - structured list of InvestigationNote entries (preserving legacy un-timestamped notes)
    """
    if not raw_findings or not raw_findings.strip():
        return None, None, []

    outcome: str | None = None
    remaining = raw_findings

    header_match = _OUTCOME_HEADER_RE.match(remaining)
    if header_match:
        outcome = header_match.group(1)
        remaining = remaining[header_match.end():]

    clean_findings = remaining.strip() or None
    if clean_findings is None:
        return outcome, None, []

    notes: list[InvestigationNote] = []
    for line in clean_findings.splitlines():
        note_match = _TIMESTAMPED_NOTE_RE.match(line)
        if note_match:
            notes.append(
                InvestigationNote(
                    timestamp=note_match.group(1),
                    author=_normalize_optional_text(note_match.group(2)),
                    content=note_match.group(3),
                )
            )
        elif notes:
            notes[-1].content = f"{notes[-1].content}\n{line}".strip()
        elif line.strip():
            notes.append(
                InvestigationNote(
                    timestamp=None,
                    author=None,
                    content=line.strip(),
                )
            )

    return outcome, clean_findings, notes


def serialize_investigation_findings(
    *,
    outcome: str | None,
    findings_text: str | None,
) -> str | None:
    """
    Combine structured outcome metadata and clean findings text for storage
    in the existing Investigation.findings Text column without schema changes.
    """
    clean_text = findings_text.strip() if findings_text and findings_text.strip() else None

    # Strip any accidental duplicate/manual outcome header from body text.
    if clean_text:
        clean_text = _OUTCOME_HEADER_RE.sub("", clean_text).strip() or None

    if outcome is not None:
        normalized_outcome = normalize_investigation_outcome(outcome)
        prefix = _OUTCOME_PREFIX_TEMPLATE.format(outcome=normalized_outcome)
        return f"{prefix}\n{clean_text}" if clean_text else prefix

    return clean_text


def format_timestamped_note(
    note: str,
    *,
    author: str | None = None,
    timestamp: datetime | None = None,
) -> str:
    """Format a single analyst note with an ISO-8601 UTC timestamp and optional author."""
    cleaned_note = note.strip()
    if not cleaned_note:
        raise ValueError("Investigation note cannot be empty.")

    # Prevent user note text from starting with the reserved outcome marker.
    cleaned_note = _OUTCOME_HEADER_RE.sub("", cleaned_note).strip()
    if not cleaned_note:
        raise ValueError("Investigation note cannot be empty.")

    ts = timestamp or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ts_str = ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    clean_author = _normalize_optional_text(author)
    if clean_author:
        return f"[{ts_str}] [by: {clean_author}] {cleaned_note}"
    return f"[{ts_str}] {cleaned_note}"


def _format_parsed_note_line(note: InvestigationNote) -> str:
    if note.timestamp is None:
        return note.content
    if note.author:
        return f"[{note.timestamp}] [by: {note.author}] {note.content}"
    return f"[{note.timestamp}] {note.content}"


def merge_investigation_findings(
    existing_raw: str | None,
    *,
    new_findings: Any,
    outcome_override: str | None = None,
) -> str | None:
    """
    Merge a findings update with existing investigation findings while preserving
    outcome metadata, prior plain findings, and all historical timestamped notes.

    - Explicit None or whitespace-only new_findings leaves existing history intact.
    - Identical updates are idempotent.
    - New findings are preserved alongside prior plain entries above timestamped notes.
    """
    existing_outcome, existing_clean, existing_notes = parse_investigation_findings(existing_raw)
    effective_outcome = outcome_override if outcome_override is not None else existing_outcome

    if new_findings is None:
        return serialize_investigation_findings(
            outcome=effective_outcome,
            findings_text=existing_clean,
        )

    if not isinstance(new_findings, str):
        raise ValueError("Investigation findings must be a string.")

    cleaned_new = _OUTCOME_HEADER_RE.sub("", new_findings.strip()).strip()
    if not cleaned_new:
        return serialize_investigation_findings(
            outcome=effective_outcome,
            findings_text=existing_clean,
        )

    if existing_clean is None:
        return serialize_investigation_findings(
            outcome=effective_outcome,
            findings_text=cleaned_new,
        )

    if cleaned_new == existing_clean:
        return serialize_investigation_findings(
            outcome=effective_outcome,
            findings_text=existing_clean,
        )

    plain_lines = [n.content for n in existing_notes if n.timestamp is None]
    ts_lines = [_format_parsed_note_line(n) for n in existing_notes if n.timestamp is not None]

    # Avoid duplicating plain findings if caller sent only the existing plain block verbatim.
    if plain_lines and cleaned_new == "\n".join(plain_lines):
        return serialize_investigation_findings(
            outcome=effective_outcome,
            findings_text=existing_clean,
        )

    addition = (
        cleaned_new[len(existing_clean):].strip()
        if cleaned_new.startswith(existing_clean)
        else cleaned_new
    )
    if addition:
        plain_lines.append(addition)

    combined_clean = "\n".join([*plain_lines, *ts_lines])
    return serialize_investigation_findings(
        outcome=effective_outcome,
        findings_text=combined_clean,
    )


class InvestigationCreate(BaseModel):
    """Request schema for creating an investigation linked to an alert."""

    alert_id: int = Field(gt=0)
    assigned_to: str | None = Field(default=None, max_length=100)
    initial_note: str | None = None

    @field_validator("assigned_to", mode="before")
    @classmethod
    def check_assignee(cls, value: Any) -> str | None:
        return validate_assigned_to(value)

    @field_validator("initial_note", mode="before")
    @classmethod
    def normalize_initial_note(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _normalize_optional_text(value)
        return value


class InvestigationUpdate(BaseModel):
    """Request schema for partial updates to an existing investigation."""

    assigned_to: str | None = Field(default=None, max_length=100)
    status: InvestigationStatus | None = None
    findings: str | None = None
    note: str | None = None
    outcome: InvestigationOutcome | None = None

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Status must be a string.")
        stripped = value.strip()
        if not stripped:
            raise ValueError("Status cannot be empty.")
        return normalize_investigation_status(stripped)

    @field_validator("outcome", mode="before")
    @classmethod
    def validate_outcome(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Outcome must be a string.")
        return normalize_investigation_outcome(value)

    @field_validator("assigned_to", mode="before")
    @classmethod
    def check_assignee(cls, value: Any) -> str | None:
        return validate_assigned_to(value)


class InvestigationStartRequest(BaseModel):
    """Request schema for transitioning an OPEN investigation to IN_PROGRESS."""

    assigned_to: str | None = Field(default=None, max_length=100)
    note: str | None = None

    @field_validator("assigned_to", mode="before")
    @classmethod
    def check_assignee(cls, value: Any) -> str | None:
        return validate_assigned_to(value)

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _normalize_optional_text(value)
        return value


class InvestigationAssignRequest(BaseModel):
    """Request schema for assigning, reassigning, or explicitly unassigning an analyst."""

    assigned_to: str | None = Field(..., max_length=100)
    note: str | None = None
    author: str | None = Field(default=None, max_length=100)

    @field_validator("assigned_to", mode="before")
    @classmethod
    def check_assignee(cls, value: Any) -> str | None:
        return validate_assigned_to(value)

    @field_validator("note", "author", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _normalize_optional_text(value)
        return value


class InvestigationNoteCreate(BaseModel):
    """Request schema for appending a timestamped investigation note."""

    note: str = Field(min_length=1)
    author: str | None = Field(default=None, max_length=100)

    @field_validator("note")
    @classmethod
    def require_non_empty_note(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Investigation note cannot be empty.")
        return stripped

    @field_validator("author", mode="before")
    @classmethod
    def normalize_author(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _normalize_optional_text(value)
        return value


class InvestigationResolveRequest(BaseModel):
    """Request schema for resolving an investigation with a final outcome."""

    outcome: InvestigationOutcome
    findings: str | None = None
    assigned_to: str | None = Field(default=None, max_length=100)
    author: str | None = Field(default=None, max_length=100)

    @field_validator("outcome", mode="before")
    @classmethod
    def validate_outcome(cls, value: Any) -> Any:
        if not isinstance(value, str):
            raise ValueError("Outcome must be a valid string.")
        return normalize_investigation_outcome(value)

    @field_validator("assigned_to", mode="before")
    @classmethod
    def check_assignee(cls, value: Any) -> str | None:
        return validate_assigned_to(value)

    @field_validator("findings", "author", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _normalize_optional_text(value)
        return value


class LinkedTransactionSummary(BaseModel):
    """Read-only summary of the transaction linked to an investigation's alert."""

    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    customer_id: str
    amount: float
    merchant_category: str
    device_id: str
    location: str
    timestamp: datetime
    payment_method: str
    transaction_type: str
    fraud_prediction: int


class LinkedAlertSummary(BaseModel):
    """Read-only summary of the alert linked to an investigation."""

    model_config = ConfigDict(from_attributes=True)

    alert_id: int
    transaction_id: str
    alert_type: str
    status: str
    created_at: datetime
    transaction: LinkedTransactionSummary | None = None


class InvestigationResponse(BaseModel):
    """Response schema preserving Phase 6 fields while exposing outcome, notes, and optional context."""

    model_config = ConfigDict(from_attributes=True)

    investigation_id: int
    alert_id: int
    assigned_to: str | None
    status: str
    findings: str | None
    outcome: InvestigationOutcome | None = None
    notes: list[InvestigationNote] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    alert: LinkedAlertSummary | None = None

    @model_validator(mode="before")
    @classmethod
    def parse_orm_or_dict(cls, data: Any) -> Any:
        """
        Parse structured outcome metadata and notes from raw findings while safely
        including linked alert/transaction context only when eager-loaded.
        """
        if isinstance(data, dict):
            raw_findings = data.get("findings")
            parsed_outcome, clean_findings, parsed_notes = parse_investigation_findings(raw_findings)
            result = dict(data)
            result["findings"] = clean_findings
            if result.get("outcome") is None:
                result["outcome"] = parsed_outcome
            if "notes" not in result or not result["notes"]:
                result["notes"] = parsed_notes
            return result

        # Inspect SQLAlchemy state to prevent unintended lazy loads or DetachedInstanceError.
        insp = sa_inspect(data, raiseerr=False)
        raw_findings = getattr(data, "findings", None)
        parsed_outcome, clean_findings, parsed_notes = parse_investigation_findings(raw_findings)

        alert_summary: LinkedAlertSummary | None = None
        alert_loaded = insp is None or "alert" not in insp.unloaded
        if alert_loaded:
            alert_obj = getattr(data, "alert", None)
            if alert_obj is not None:
                alert_insp = sa_inspect(alert_obj, raiseerr=False)
                tx_summary: LinkedTransactionSummary | None = None
                tx_loaded = alert_insp is None or "transaction" not in alert_insp.unloaded
                if tx_loaded:
                    tx_obj = getattr(alert_obj, "transaction", None)
                    if tx_obj is not None:
                        tx_summary = LinkedTransactionSummary.model_validate(tx_obj)

                alert_summary = LinkedAlertSummary(
                    alert_id=alert_obj.alert_id,
                    transaction_id=alert_obj.transaction_id,
                    alert_type=alert_obj.alert_type,
                    status=alert_obj.status,
                    created_at=alert_obj.created_at,
                    transaction=tx_summary,
                )

        return {
            "investigation_id": data.investigation_id,
            "alert_id": data.alert_id,
            "assigned_to": data.assigned_to,
            "status": data.status,
            "findings": clean_findings,
            "outcome": parsed_outcome,
            "notes": parsed_notes,
            "created_at": data.created_at,
            "updated_at": data.updated_at,
            "alert": alert_summary,
        }
