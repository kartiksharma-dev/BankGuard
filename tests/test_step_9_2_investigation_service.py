from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base
from backend.app.models import Alert, Customer, Investigation, Transaction
from backend.app.schemas.investigation import (
    InvestigationCreate,
    InvestigationNoteCreate,
    InvestigationResolveRequest,
    InvestigationResponse,
    InvestigationStartRequest,
    InvestigationUpdate,
    merge_investigation_findings,
    parse_investigation_findings,
)
from backend.app.services.investigation_service import (
    InvestigationAlertSyncError,
    InvestigationConflictError,
    InvestigationNotFoundError,
    InvestigationValidationError,
    add_investigation_note,
    assign_investigation,
    create_investigation,
    get_investigation_by_id,
    list_investigations,
    resolve_investigation,
    start_investigation,
    update_investigation,
)


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite session for Phase 9.2 investigation service tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _seed_alert(
    db,
    *,
    tx_id: str = "TX-INV-9001",
    customer_id: str = "CUST-INV-9001",
    alert_type: str = "ML_FRAUD_DETECTED",
) -> Alert:
    customer = db.get(Customer, customer_id)
    if customer is None:
        customer = Customer(customer_id=customer_id)
        db.add(customer)
        db.flush()

    tx = db.get(Transaction, tx_id)
    if tx is None:
        tx = Transaction(
            transaction_id=tx_id,
            customer_id=customer_id,
            amount=48500.0,
            merchant_category="electronics",
            device_id="DEV-99",
            location="Mumbai",
            timestamp=datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc),
            payment_method="credit_card",
            transaction_type="purchase",
            oldbalance_org=100000.0,
            newbalance_orig=51500.0,
            oldbalance_dest=10000.0,
            newbalance_dest=58500.0,
            step=1,
            fraud_prediction=1,
        )
        db.add(tx)
        db.flush()

    alert = Alert(
        transaction_id=tx_id,
        alert_type=alert_type,
        status="OPEN",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


# ---------------------------------------------------------------------------
# 1. Creation, Assignment & Duplicate Prevention
# ---------------------------------------------------------------------------

def test_create_investigation_with_initial_note_and_assignment(db_session):
    """Creating an investigation initializes status=OPEN and preserves initial timestamped note."""
    alert = _seed_alert(db_session)

    inv = create_investigation(
        db_session,
        alert_id=alert.alert_id,
        assigned_to="  analyst_alpha  ",
        initial_note="Initial triage escalated.",
    )

    assert inv.investigation_id > 0
    assert inv.alert_id == alert.alert_id
    assert inv.assigned_to == "analyst_alpha"
    assert inv.status == "OPEN"

    resp = InvestigationResponse.model_validate(inv)
    assert resp.outcome is None
    assert len(resp.notes) == 1
    assert resp.notes[0].timestamp is not None
    assert resp.notes[0].author == "analyst_alpha"
    assert resp.notes[0].content == "Initial triage escalated."


def test_create_investigation_missing_alert_raises_not_found(db_session):
    """Creating an investigation for an unknown alert raises InvestigationNotFoundError."""
    with pytest.raises(InvestigationNotFoundError, match="Alert not found"):
        create_investigation(db_session, alert_id=99999)


def test_create_investigation_duplicate_alert_raises_conflict(db_session):
    """Creating a second investigation for the same alert raises InvestigationConflictError."""
    alert = _seed_alert(db_session)
    create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_1")

    with pytest.raises(InvestigationConflictError, match="already exists"):
        create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_2")


def test_assign_investigation_updates_and_clears_assignee(db_session):
    """Analysts can be assigned, reassigned with audit note, or unassigned cleanly."""
    alert = _seed_alert(db_session)
    inv = create_investigation(db_session, alert_id=alert.alert_id)
    assert inv.assigned_to is None

    assigned = assign_investigation(
        db_session,
        inv.investigation_id,
        assigned_to="analyst_one",
        note="Picked up from queue.",
    )
    assert assigned.assigned_to == "analyst_one"

    cleared = assign_investigation(
        db_session,
        inv.investigation_id,
        assigned_to=None,
    )
    assert cleared.assigned_to is None
    resp = InvestigationResponse.model_validate(cleared)
    assert "Picked up from queue." in resp.findings


# ---------------------------------------------------------------------------
# 2. Lifecycle Validation & Status Transitions (OPEN -> IN_PROGRESS -> RESOLVED)
# ---------------------------------------------------------------------------

def test_start_investigation_transitions_open_to_in_progress(db_session):
    """Starting an OPEN investigation moves it to IN_PROGRESS and keeps alert OPEN."""
    alert = _seed_alert(db_session)
    inv = create_investigation(db_session, alert_id=alert.alert_id)

    started = start_investigation(
        db_session,
        inv.investigation_id,
        assigned_to="analyst_sarah",
        note="Started device fingerprint check.",
    )

    assert started.status == "IN_PROGRESS"
    assert started.assigned_to == "analyst_sarah"
    db_session.refresh(alert)
    assert alert.status == "OPEN"


def test_cannot_resolve_directly_from_open(db_session):
    """Skipping IN_PROGRESS (OPEN -> RESOLVED) is rejected by lifecycle rules."""
    alert = _seed_alert(db_session)
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_1")

    with pytest.raises(InvestigationValidationError, match="Invalid status transition"):
        resolve_investigation(
            db_session,
            inv.investigation_id,
            outcome="CONFIRMED_FRAUD",
            findings="Trying to skip IN_PROGRESS.",
        )

    with pytest.raises(InvestigationValidationError, match="Invalid status transition"):
        update_investigation(
            db_session,
            inv.investigation_id,
            status="RESOLVED",
            outcome="CONFIRMED_FRAUD",
            findings="Trying via update_investigation.",
        )

    db_session.refresh(inv)
    db_session.refresh(alert)
    assert inv.status == "OPEN"
    assert alert.status == "OPEN"


def test_cannot_start_already_started_or_resolved_investigation(db_session):
    """start_investigation rejects investigations that are already IN_PROGRESS or RESOLVED."""
    alert = _seed_alert(db_session)
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_1")
    start_investigation(db_session, inv.investigation_id)

    with pytest.raises(InvestigationValidationError, match="Only OPEN investigations can be started"):
        start_investigation(db_session, inv.investigation_id)

    resolve_investigation(
        db_session,
        inv.investigation_id,
        outcome="LEGITIMATE",
        findings="Verified with customer.",
    )

    with pytest.raises(InvestigationValidationError, match="Only OPEN investigations can be started"):
        start_investigation(db_session, inv.investigation_id)


def test_cannot_modify_or_transition_resolved_investigation(db_session):
    """Resolved investigations are terminal and reject status, assignee, note, or resolution changes."""
    alert = _seed_alert(db_session)
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_1")
    start_investigation(db_session, inv.investigation_id)
    resolve_investigation(
        db_session,
        inv.investigation_id,
        outcome="CONFIRMED_FRAUD",
        findings="Unauthorized transfer confirmed.",
    )

    with pytest.raises(InvestigationValidationError, match="cannot be modified"):
        assign_investigation(db_session, inv.investigation_id, assigned_to="analyst_2")

    with pytest.raises(InvestigationValidationError, match="cannot be modified"):
        add_investigation_note(db_session, inv.investigation_id, note="Late note")

    with pytest.raises(InvestigationValidationError, match="cannot be modified"):
        update_investigation(db_session, inv.investigation_id, status="IN_PROGRESS")

    with pytest.raises(InvestigationValidationError, match="Invalid status transition|cannot transition"):
        resolve_investigation(
            db_session,
            inv.investigation_id,
            outcome="LEGITIMATE",
            findings="Re-resolving",
        )


def test_invalid_status_outcome_and_partial_update_constraints(db_session):
    """Schema and service reject unknown statuses, invalid outcomes, and premature outcomes."""
    alert = _seed_alert(db_session)
    inv = create_investigation(db_session, alert_id=alert.alert_id)
    start_investigation(db_session, inv.investigation_id)

    # Recording outcome while remaining IN_PROGRESS is rejected
    with pytest.raises(InvestigationValidationError, match="only be recorded when resolving"):
        update_investigation(
            db_session,
            inv.investigation_id,
            status="IN_PROGRESS",
            outcome="CONFIRMED_FRAUD",
            findings="Premature outcome",
        )

    # Invalid status and outcome via service
    with pytest.raises(InvestigationValidationError, match="Invalid investigation status"):
        update_investigation(db_session, inv.investigation_id, status="ARCHIVED")

    with pytest.raises(InvestigationValidationError, match="Invalid investigation outcome"):
        resolve_investigation(
            db_session,
            inv.investigation_id,
            outcome="MAYBE_FRAUD",
            findings="Uncertain",
        )

    # Schema validation checks
    with pytest.raises(ValidationError):
        InvestigationUpdate(status="UNKNOWN_STATUS")

    with pytest.raises(ValidationError):
        InvestigationResolveRequest(outcome="UNKNOWN_OUTCOME", findings="test")

    with pytest.raises(ValidationError):
        InvestigationNoteCreate(note="   ")


# ---------------------------------------------------------------------------
# 3. Timestamped Notes & Backward Compatibility
# ---------------------------------------------------------------------------

def test_timestamped_notes_append_without_overwriting(db_session):
    """Appending multiple notes retains chronological entries without overwriting prior text."""
    alert = _seed_alert(db_session)
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_1")
    start_investigation(db_session, inv.investigation_id)

    t1 = datetime(2026, 11, 27, 1, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 27, 1, 15, 0, tzinfo=timezone.utc)

    add_investigation_note(
        db_session,
        inv.investigation_id,
        note="Checked IP geolocation mismatch.",
        author="analyst_1",
        timestamp=t1,
    )
    updated = add_investigation_note(
        db_session,
        inv.investigation_id,
        note="Called cardholder; verified suspicious login.",
        author="lead_analyst",
        timestamp=t2,
    )

    resp = InvestigationResponse.model_validate(updated)
    assert len(resp.notes) == 2
    assert resp.notes[0].timestamp == "2026-11-27T01:00:00Z"
    assert resp.notes[0].author == "analyst_1"
    assert resp.notes[0].content == "Checked IP geolocation mismatch."
    assert resp.notes[1].timestamp == "2026-11-27T01:15:00Z"
    assert resp.notes[1].author == "lead_analyst"
    assert resp.notes[1].content == "Called cardholder; verified suspicious login."


def test_backward_compatibility_with_legacy_findings_and_closed_status(db_session):
    """Legacy plain findings strings and CLOSED status deserialize cleanly and preserve prior text."""
    alert1 = _seed_alert(db_session, tx_id="TX-LEG-1")
    alert2 = _seed_alert(db_session, tx_id="TX-LEG-2")

    legacy_closed = Investigation(
        alert_id=alert1.alert_id,
        assigned_to="legacy_analyst",
        status="CLOSED",
        findings="Legacy verification note.\nSecond line detail.",
    )
    legacy_active = Investigation(
        alert_id=alert2.alert_id,
        assigned_to="legacy_analyst",
        status="IN_PROGRESS",
        findings="Initial plain findings text.",
    )
    db_session.add_all([legacy_closed, legacy_active])
    db_session.commit()
    db_session.refresh(legacy_closed)
    db_session.refresh(legacy_active)

    closed_resp = InvestigationResponse.model_validate(legacy_closed)
    assert closed_resp.status == "CLOSED"
    assert closed_resp.outcome is None
    assert closed_resp.findings == "Legacy verification note.\nSecond line detail."
    assert len(closed_resp.notes) == 1
    assert closed_resp.notes[0].timestamp is None
    assert closed_resp.notes[0].content == "Legacy verification note.\nSecond line detail."

    # Appending a note onto legacy plain text preserves original text intact
    t_append = datetime(2026, 11, 27, 2, 0, 0, tzinfo=timezone.utc)
    updated = add_investigation_note(
        db_session,
        legacy_active.investigation_id,
        note="Follow-up call completed.",
        timestamp=t_append,
    )
    active_resp = InvestigationResponse.model_validate(updated)
    assert len(active_resp.notes) == 2
    assert active_resp.notes[0].timestamp is None
    assert active_resp.notes[0].content == "Initial plain findings text."
    assert active_resp.notes[1].timestamp == "2026-11-27T02:00:00Z"
    assert active_resp.notes[1].content == "Follow-up call completed."


def test_detached_orm_serialization_does_not_trigger_lazy_load():
    """Detached Investigation objects serialize cleanly with alert=None and parsed outcome."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    try:
        with Session() as db:
            alert = _seed_alert(db, tx_id="TX-DETACH-1")
            inv = create_investigation(db, alert_id=alert.alert_id, assigned_to="a1")
            start_investigation(db, inv.investigation_id)
            resolved = resolve_investigation(
                db,
                inv.investigation_id,
                outcome="CONFIRMED_FRAUD",
                findings="Detached test confirmed.",
            )
            inv_id = resolved.investigation_id

        # Fetch in a new session then close the session BEFORE calling model_validate
        with Session() as db2:
            detached_inv = db2.get(Investigation, inv_id)

        resp = InvestigationResponse.model_validate(detached_inv)
        assert resp.status == "RESOLVED"
        assert resp.outcome == "CONFIRMED_FRAUD"
        assert resp.alert is None
        assert "Detached test confirmed." in resp.findings
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ---------------------------------------------------------------------------
# 4. Outcome Serialization, Resolution Requirements & Atomic Alert Sync
# ---------------------------------------------------------------------------

def test_resolve_requires_findings_and_uses_existing_notes_when_present(db_session):
    """Resolution rejects missing findings, or preserves prior notes if resolved without extra text."""
    alert1 = _seed_alert(db_session, tx_id="TX-REQ-1")
    inv1 = create_investigation(db_session, alert_id=alert1.alert_id, assigned_to="a1")
    start_investigation(db_session, inv1.investigation_id)

    with pytest.raises(InvestigationValidationError, match="findings are required"):
        resolve_investigation(
            db_session,
            inv1.investigation_id,
            outcome="CONFIRMED_FRAUD",
            findings="   ",
        )

    db_session.refresh(inv1)
    db_session.refresh(alert1)
    assert inv1.status == "IN_PROGRESS"
    assert alert1.status == "OPEN"

    # Add findings first, then resolve without supplying additional findings text
    add_investigation_note(
        db_session,
        inv1.investigation_id,
        note="Prior note confirms legitimate travel.",
    )
    resolved = resolve_investigation(
        db_session,
        inv1.investigation_id,
        outcome="LEGITIMATE",
        findings=None,
    )

    resp = InvestigationResponse.model_validate(resolved)
    assert resp.status == "RESOLVED"
    assert resp.outcome == "LEGITIMATE"
    assert "Prior note confirms legitimate travel." in resp.findings
    assert resolved.alert.status == "DISMISSED"


def test_resolve_confirmed_fraud_and_legitimate_sync_alert_and_filter_by_outcome(db_session):
    """Resolving encodes outcome inside findings, syncs Alert status, and supports outcome filtering."""
    alert_fraud = _seed_alert(db_session, tx_id="TX-OUT-1")
    alert_legit = _seed_alert(db_session, tx_id="TX-OUT-2")

    inv_fraud = create_investigation(db_session, alert_id=alert_fraud.alert_id, assigned_to="a1")
    inv_legit = create_investigation(db_session, alert_id=alert_legit.alert_id, assigned_to="a2")

    start_investigation(db_session, inv_fraud.investigation_id, note="Checking device velocity.")
    start_investigation(db_session, inv_legit.investigation_id)

    resolved_fraud = resolve_investigation(
        db_session,
        inv_fraud.investigation_id,
        outcome="CONFIRMED_FRAUD",
        findings="Verified stolen credential takeover.",
    )
    assert resolved_fraud.findings.startswith("[OUTCOME: CONFIRMED_FRAUD]\n")
    fraud_resp = InvestigationResponse.model_validate(resolved_fraud)
    assert fraud_resp.outcome == "CONFIRMED_FRAUD"
    assert not fraud_resp.findings.startswith("[OUTCOME:")
    assert len(fraud_resp.notes) == 2
    assert fraud_resp.alert is not None
    assert fraud_resp.alert.status == "RESOLVED"
    assert fraud_resp.alert.transaction is not None
    assert fraud_resp.alert.transaction.transaction_id == "TX-OUT-1"

    resolved_legit = resolve_investigation(
        db_session,
        inv_legit.investigation_id,
        outcome="legitimate",
        findings="Cardholder confirmed travel purchase.",
    )
    assert resolved_legit.findings.startswith("[OUTCOME: LEGITIMATE]\n")
    legit_resp = InvestigationResponse.model_validate(resolved_legit)
    assert legit_resp.outcome == "LEGITIMATE"
    assert legit_resp.alert is not None
    assert legit_resp.alert.status == "DISMISSED"

    # Alert statuses synchronized atomically in DB
    db_session.refresh(alert_fraud)
    db_session.refresh(alert_legit)
    assert alert_fraud.status == "RESOLVED"
    assert alert_legit.status == "DISMISSED"

    # Outcome query filter matches cleanly in SQL
    fraud_only = list_investigations(db_session, outcome="CONFIRMED_FRAUD", include_context=True)
    legit_only = list_investigations(db_session, outcome="LEGITIMATE")
    assert [i.investigation_id for i in fraud_only] == [inv_fraud.investigation_id]
    assert [i.investigation_id for i in legit_only] == [inv_legit.investigation_id]


def test_resolve_rollback_is_atomic_on_database_commit_failure(db_session, monkeypatch):
    """If commit fails during resolution, both Investigation and Alert changes roll back atomically."""
    alert = _seed_alert(db_session, tx_id="TX-ATOMIC-1")
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="a1")
    start_investigation(db_session, inv.investigation_id)

    def failing_commit():
        raise SQLAlchemyError("Simulated commit failure")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    with pytest.raises(SQLAlchemyError, match="Simulated commit failure"):
        resolve_investigation(
            db_session,
            inv.investigation_id,
            outcome="CONFIRMED_FRAUD",
            findings="Should be rolled back.",
        )

    # Restore real commit before inspecting persisted state
    monkeypatch.undo()
    db_session.expire_all()

    persisted_inv = db_session.get(Investigation, inv.investigation_id)
    persisted_alert = db_session.get(Alert, alert.alert_id)
    assert persisted_inv.status == "IN_PROGRESS"
    assert persisted_alert.status == "OPEN"
    outcome, _, _ = parse_investigation_findings(persisted_inv.findings)
    assert outcome is None

    # Verify the same SQLAlchemy session remains reusable for subsequent writes after rollback
    after_note = add_investigation_note(
        db_session,
        inv.investigation_id,
        note="Follow-up note after commit failure rollback.",
    )
    assert after_note.status == "IN_PROGRESS"

    resolved_retry = resolve_investigation(
        db_session,
        inv.investigation_id,
        outcome="CONFIRMED_FRAUD",
        findings="Resolved cleanly after commit failure recovery.",
    )
    assert resolved_retry.status == "RESOLVED"
    assert resolved_retry.alert.status == "RESOLVED"
    retried_outcome, retried_clean, _ = parse_investigation_findings(resolved_retry.findings)
    assert retried_outcome == "CONFIRMED_FRAUD"
    assert "Follow-up note after commit failure rollback." in (retried_clean or "")


def test_list_investigations_with_context_loads_alert_and_transaction(db_session):
    """list_investigations(..., include_context=True) loads alert and transaction summaries."""
    alert = _seed_alert(db_session, tx_id="TX-CTX-1")
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="ctx_analyst")

    items = list_investigations(db_session, include_context=True)
    assert len(items) == 1

    resp = InvestigationResponse.model_validate(items[0])
    assert resp.alert is not None
    assert resp.alert.alert_id == alert.alert_id
    assert resp.alert.alert_type == "ML_FRAUD_DETECTED"
    assert resp.alert.transaction is not None
    assert resp.alert.transaction.transaction_id == "TX-CTX-1"
    assert resp.alert.transaction.amount == 48500.0


def test_update_investigation_supports_partial_update_note_and_resolution(db_session):
    """update_investigation supports Phase 6 findings edits, note appending, and full resolution."""
    alert = _seed_alert(db_session, tx_id="TX-UPD-1")
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="a1")

    # Empty call fails
    with pytest.raises(InvestigationValidationError, match="At least one field"):
        update_investigation(db_session, inv.investigation_id)

    # Start via update_investigation with plain findings
    in_prog = update_investigation(
        db_session,
        inv.investigation_id,
        status="in_progress",
        findings="Initial manual review text.",
    )
    assert in_prog.status == "IN_PROGRESS"

    # Append timestamped note without erasing existing plain findings, then resolve
    resolved = update_investigation(
        db_session,
        inv.investigation_id,
        status="RESOLVED",
        outcome="CONFIRMED_FRAUD",
        note="Escalated and confirmed unauthorized device.",
    )
    resp = InvestigationResponse.model_validate(resolved)
    assert resp.status == "RESOLVED"
    assert resp.outcome == "CONFIRMED_FRAUD"
    assert len(resp.notes) == 2
    assert resp.notes[0].content == "Initial manual review text."
    assert resp.notes[1].content == "Escalated and confirmed unauthorized device."
    assert resp.alert is not None
    assert resp.alert.status == "RESOLVED"


# ---------------------------------------------------------------------------
# 5. Final Code Review Regression Tests (Issues 1, 2 & 3)
# ---------------------------------------------------------------------------

def test_assignee_validation_across_all_operations_and_schemas(db_session):
    """Issue 1: Reject >100 chars and whitespace-only assignees; support None unassign & preserve existing."""
    alert = _seed_alert(db_session, tx_id="TX-ASSN-1")
    too_long = "a" * 101
    exact_limit = "a" * 100

    # Schema checks
    for bad_val in ("", "   ", too_long):
        with pytest.raises(ValidationError):
            InvestigationCreate(alert_id=alert.alert_id, assigned_to=bad_val)
        with pytest.raises(ValidationError):
            InvestigationUpdate(assigned_to=bad_val)
        with pytest.raises(ValidationError):
            InvestigationStartRequest(assigned_to=bad_val)
        with pytest.raises(ValidationError):
            InvestigationResolveRequest(outcome="LEGITIMATE", assigned_to=bad_val)

    # create_investigation validation
    with pytest.raises(InvestigationValidationError, match="100 characters"):
        create_investigation(db_session, alert_id=alert.alert_id, assigned_to=too_long)
    with pytest.raises(InvestigationValidationError, match="whitespace-only"):
        create_investigation(db_session, alert_id=alert.alert_id, assigned_to="   ")

    # Exact 100 characters succeeds (with surrounding spaces trimmed)
    inv = create_investigation(
        db_session,
        alert_id=alert.alert_id,
        assigned_to=f"  {exact_limit}  ",
    )
    assert inv.assigned_to == exact_limit

    # assign_investigation rejects bad values without clobbering existing assignment
    with pytest.raises(InvestigationValidationError, match="100 characters"):
        assign_investigation(db_session, inv.investigation_id, assigned_to=too_long)
    with pytest.raises(InvestigationValidationError, match="whitespace-only"):
        assign_investigation(db_session, inv.investigation_id, assigned_to="   ")
    db_session.refresh(inv)
    assert inv.assigned_to == exact_limit

    # Explicit None unassigns cleanly
    unassigned = assign_investigation(db_session, inv.investigation_id, assigned_to=None)
    assert unassigned.assigned_to is None
    reassigned = assign_investigation(db_session, inv.investigation_id, assigned_to="primary_analyst")
    assert reassigned.assigned_to == "primary_analyst"

    # start_investigation rejects invalid assignees and preserves existing when omitted
    with pytest.raises(InvestigationValidationError, match="100 characters"):
        start_investigation(db_session, inv.investigation_id, assigned_to=too_long)
    with pytest.raises(InvestigationValidationError, match="whitespace-only"):
        start_investigation(db_session, inv.investigation_id, assigned_to="   ")
    started = start_investigation(db_session, inv.investigation_id)
    assert started.status == "IN_PROGRESS"
    assert started.assigned_to == "primary_analyst"

    # update_investigation rejects invalid assignees, preserves existing, and supports None unassign
    with pytest.raises(InvestigationValidationError, match="100 characters"):
        update_investigation(db_session, inv.investigation_id, assigned_to=too_long)
    with pytest.raises(InvestigationValidationError, match="whitespace-only"):
        update_investigation(db_session, inv.investigation_id, assigned_to="")
    db_session.refresh(inv)
    assert inv.assigned_to == "primary_analyst"

    cleared = update_investigation(db_session, inv.investigation_id, assigned_to=None)
    assert cleared.assigned_to is None

    # resolve_investigation preserves existing assignee when omitted and validates if provided
    assign_investigation(db_session, inv.investigation_id, assigned_to="closing_analyst")
    with pytest.raises(InvestigationValidationError, match="100 characters"):
        resolve_investigation(
            db_session,
            inv.investigation_id,
            outcome="LEGITIMATE",
            findings="Test",
            assigned_to=too_long,
        )
    resolved = resolve_investigation(
        db_session,
        inv.investigation_id,
        outcome="LEGITIMATE",
        findings="Verified by closing analyst.",
    )
    assert resolved.assigned_to == "closing_analyst"


def test_findings_updates_preserve_historical_notes_and_multiple_updates(db_session):
    """Issue 2: Updating findings preserves all prior timestamped notes and earlier findings entries."""
    alert = _seed_alert(db_session, tx_id="TX-HIST-1")
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_hist")
    start_investigation(db_session, inv.investigation_id)

    t1 = datetime(2026, 11, 27, 3, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 27, 3, 10, 0, tzinfo=timezone.utc)

    add_investigation_note(db_session, inv.investigation_id, note="Timestamped note A.", timestamp=t1)
    add_investigation_note(db_session, inv.investigation_id, note="Timestamped note B.", timestamp=t2)

    # First findings update must NOT erase timestamped notes A & B
    after_f1 = update_investigation(
        db_session,
        inv.investigation_id,
        findings="First summary finding.",
    )
    resp1 = InvestigationResponse.model_validate(after_f1)
    assert "First summary finding." in resp1.findings
    assert [n.content for n in resp1.notes if n.timestamp] == [
        "Timestamped note A.",
        "Timestamped note B.",
    ]

    # Second distinct findings update must preserve First summary finding AND timestamped notes
    after_f2 = update_investigation(
        db_session,
        inv.investigation_id,
        findings="Second summary finding.",
    )
    resp2 = InvestigationResponse.model_validate(after_f2)
    assert "First summary finding." in resp2.findings
    assert "Second summary finding." in resp2.findings
    assert [n.content for n in resp2.notes if n.timestamp] == [
        "Timestamped note A.",
        "Timestamped note B.",
    ]

    # Appending another note preserves both summary findings and earlier notes
    t3 = datetime(2026, 11, 27, 3, 20, 0, tzinfo=timezone.utc)
    after_n3 = add_investigation_note(db_session, inv.investigation_id, note="Timestamped note C.", timestamp=t3)
    resp3 = InvestigationResponse.model_validate(after_n3)
    assert "First summary finding." in resp3.findings
    assert "Second summary finding." in resp3.findings
    assert [n.content for n in resp3.notes if n.timestamp] == [
        "Timestamped note A.",
        "Timestamped note B.",
        "Timestamped note C.",
    ]


def test_explicit_null_and_idempotent_findings_preserve_history(db_session):
    """Issue 2: Explicit None or whitespace findings updates never erase historical notes."""
    alert = _seed_alert(db_session, tx_id="TX-NULL-1")
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_null")
    start_investigation(db_session, inv.investigation_id, note="Protected historical note.")

    # Explicit findings=None during status/assignee update
    updated_null = update_investigation(
        db_session,
        inv.investigation_id,
        assigned_to="analyst_null_2",
        findings=None,
    )
    resp_null = InvestigationResponse.model_validate(updated_null)
    assert resp_null.assigned_to == "analyst_null_2"
    assert len(resp_null.notes) == 1
    assert resp_null.notes[0].content == "Protected historical note."

    # Whitespace-only findings update also preserves existing history
    updated_ws = update_investigation(
        db_session,
        inv.investigation_id,
        findings="   ",
    )
    resp_ws = InvestigationResponse.model_validate(updated_ws)
    assert len(resp_ws.notes) == 1
    assert resp_ws.notes[0].content == "Protected historical note."

    # Re-sending identical findings text does not duplicate entries
    updated_same = update_investigation(
        db_session,
        inv.investigation_id,
        findings=resp_ws.findings,
    )
    resp_same = InvestigationResponse.model_validate(updated_same)
    assert len(resp_same.notes) == 1


def test_outcome_metadata_survives_findings_updates(db_session):
    """Issue 2: Structured outcome metadata survives findings merges and updates."""
    raw_with_outcome = "[OUTCOME: CONFIRMED_FRAUD]\n[2026-11-27T01:00:00Z] Initial evidence."
    merged = merge_investigation_findings(
        raw_with_outcome,
        new_findings="Additional post-review finding.",
    )
    outcome, clean, notes = parse_investigation_findings(merged)
    assert outcome == "CONFIRMED_FRAUD"
    assert "Additional post-review finding." in clean
    assert any(n.timestamp == "2026-11-27T01:00:00Z" and n.content == "Initial evidence." for n in notes)

    # Explicit null merge also preserves outcome metadata
    merged_null = merge_investigation_findings(merged, new_findings=None)
    outcome2, clean2, _ = parse_investigation_findings(merged_null)
    assert outcome2 == "CONFIRMED_FRAUD"
    assert clean2 == clean

    # Mutable row carrying outcome metadata preserves it across update_investigation(findings=...)
    alert = _seed_alert(db_session, tx_id="TX-OUTSURV-1")
    inv = Investigation(
        alert_id=alert.alert_id,
        assigned_to="analyst_surv",
        status="IN_PROGRESS",
        findings="[OUTCOME: CONFIRMED_FRAUD]\n[2026-11-27T01:00:00Z] Seeded evidence.",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    updated = update_investigation(
        db_session,
        inv.investigation_id,
        findings="Supplemental findings note.",
    )
    resp = InvestigationResponse.model_validate(updated)
    assert resp.outcome == "CONFIRMED_FRAUD"
    assert "Supplemental findings note." in resp.findings
    assert any(n.content == "Seeded evidence." and n.timestamp is not None for n in resp.notes)


def test_resolve_rollback_on_alert_sync_failure_and_session_recovery(db_session, monkeypatch):
    """Issue 3: Failed alert sync rolls back atomically and leaves db_session reusable."""
    alert = _seed_alert(db_session, tx_id="TX-SYNCFAIL-1")
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_sync")
    start_investigation(db_session, inv.investigation_id, note="Initial check completed.")

    def broken_sync(db, investigation, outcome):
        raise RuntimeError("Simulated alert status constraint or lock failure")

    monkeypatch.setattr(
        "backend.app.services.investigation_service._sync_alert_status",
        broken_sync,
    )

    with pytest.raises(InvestigationAlertSyncError, match="Failed to synchronize linked alert"):
        resolve_investigation(
            db_session,
            inv.investigation_id,
            outcome="CONFIRMED_FRAUD",
            findings="Final confirmed fraud findings.",
        )

    # Restore sync and inspect persisted DB state directly on the SAME session
    monkeypatch.undo()

    persisted_inv = db_session.get(Investigation, inv.investigation_id)
    persisted_alert = db_session.get(Alert, alert.alert_id)
    assert persisted_inv.status == "IN_PROGRESS"
    assert persisted_alert.status == "OPEN"
    outcome, clean, _ = parse_investigation_findings(persisted_inv.findings)
    assert outcome is None
    assert "Final confirmed fraud findings." not in (clean or "")

    # The same session must cleanly execute new transactions afterward (no PendingRollbackError)
    after_note = add_investigation_note(
        db_session,
        inv.investigation_id,
        note="Retrying after transient lock cleared.",
    )
    assert after_note.status == "IN_PROGRESS"

    resolved_retry = resolve_investigation(
        db_session,
        inv.investigation_id,
        outcome="CONFIRMED_FRAUD",
        findings="Resolved cleanly on retry.",
    )
    assert resolved_retry.status == "RESOLVED"
    assert resolved_retry.alert.status == "RESOLVED"


def test_update_investigation_resolution_rollback_on_alert_sync_failure(db_session, monkeypatch):
    """Failed alert sync via update_investigation(..., status='RESOLVED') rolls back atomically."""
    alert = _seed_alert(db_session, tx_id="TX-UPDATE-SYNCFAIL-1")
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_update")
    start_investigation(db_session, inv.investigation_id, note="Ready for update resolution.")

    def broken_sync(db, investigation, outcome):
        raise RuntimeError("Simulated update alert sync failure")

    monkeypatch.setattr(
        "backend.app.services.investigation_service._sync_alert_status",
        broken_sync,
    )

    with pytest.raises(InvestigationAlertSyncError, match="Failed to synchronize linked alert"):
        update_investigation(
            db_session,
            inv.investigation_id,
            status="RESOLVED",
            outcome="CONFIRMED_FRAUD",
            findings="Update findings that must roll back.",
        )

    monkeypatch.undo()
    db_session.expire_all()

    persisted_inv = db_session.get(Investigation, inv.investigation_id)
    persisted_alert = db_session.get(Alert, alert.alert_id)
    assert persisted_inv.status == "IN_PROGRESS"
    assert persisted_alert.status == "OPEN"
    outcome, clean, _ = parse_investigation_findings(persisted_inv.findings)
    assert outcome is None
    assert "Update findings that must roll back." not in (clean or "")

    after_note = add_investigation_note(
        db_session,
        inv.investigation_id,
        note="Recovered after update sync failure.",
    )
    assert after_note.status == "IN_PROGRESS"

    resolved_retry = update_investigation(
        db_session,
        inv.investigation_id,
        status="RESOLVED",
        outcome="CONFIRMED_FRAUD",
        findings="Resolved via update_investigation after recovery.",
    )
    assert resolved_retry.status == "RESOLVED"
    assert resolved_retry.alert.status == "RESOLVED"
    retry_outcome, retry_clean, _ = parse_investigation_findings(resolved_retry.findings)
    assert retry_outcome == "CONFIRMED_FRAUD"
    assert "Recovered after update sync failure." in (retry_clean or "")


def test_resolve_missing_linked_alert_raises_not_found_and_rolls_back(db_session):
    """Resolving when linked alert is missing raises InvestigationNotFoundError, rolls back, and keeps session reusable."""
    alert = _seed_alert(db_session, tx_id="TX-MISSING-ALERT-1")
    # Seed a second alert so deleting alert_id=1 does not make SQLite reuse alert_id=1 later
    _seed_alert(db_session, tx_id="TX-MISSING-ALERT-ANCHOR")
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_missing")
    start_investigation(db_session, inv.investigation_id, note="Started before alert removal.")

    # Delete the parent alert row via Core SQL so Investigation stays orphan-linked for _sync_alert_status()
    db_session.execute(delete(Alert).where(Alert.alert_id == alert.alert_id))
    db_session.commit()
    db_session.expire_all()

    with pytest.raises(InvestigationNotFoundError, match="Linked alert"):
        resolve_investigation(
            db_session,
            inv.investigation_id,
            outcome="LEGITIMATE",
            findings="Attempted resolution without alert.",
        )

    db_session.expire_all()
    persisted_inv = db_session.get(Investigation, inv.investigation_id)
    assert persisted_inv.status == "IN_PROGRESS"
    outcome, clean, _ = parse_investigation_findings(persisted_inv.findings)
    assert outcome is None
    assert "Attempted resolution without alert." not in (clean or "")

    # Verify the same session can still execute transactions cleanly afterward
    note_after = add_investigation_note(
        db_session,
        inv.investigation_id,
        note="Session remains usable after missing-alert rollback.",
    )
    assert note_after.status == "IN_PROGRESS"

    replacement_alert = _seed_alert(db_session, tx_id="TX-MISSING-ALERT-RECOVERY")
    recovery_inv = create_investigation(
        db_session,
        alert_id=replacement_alert.alert_id,
        assigned_to="analyst_recovery",
    )
    assert recovery_inv.status == "OPEN"
    assert recovery_inv.assigned_to == "analyst_recovery"


def test_resolve_rollback_on_alert_sync_flush_failure_and_session_recovery(db_session, monkeypatch):
    """Database flush() failure inside _sync_alert_status rolls back atomically and keeps session reusable."""
    alert = _seed_alert(db_session, tx_id="TX-FLUSHFAIL-1")
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_flush")
    start_investigation(db_session, inv.investigation_id, note="Initial check before flush failure.")

    def failing_flush(*args, **kwargs):
        raise SQLAlchemyError("Simulated alert sync flush failure")

    monkeypatch.setattr(db_session, "flush", failing_flush)

    with pytest.raises(InvestigationAlertSyncError, match="Failed to synchronize linked alert"):
        resolve_investigation(
            db_session,
            inv.investigation_id,
            outcome="CONFIRMED_FRAUD",
            findings="Flush failure findings must roll back.",
        )

    monkeypatch.undo()
    db_session.expire_all()

    persisted_inv = db_session.get(Investigation, inv.investigation_id)
    persisted_alert = db_session.get(Alert, alert.alert_id)
    assert persisted_inv.status == "IN_PROGRESS"
    assert persisted_alert.status == "OPEN"
    outcome, clean, _ = parse_investigation_findings(persisted_inv.findings)
    assert outcome is None
    assert "Flush failure findings must roll back." not in (clean or "")

    after_note = add_investigation_note(
        db_session,
        inv.investigation_id,
        note="Recovered after flush failure.",
    )
    assert after_note.status == "IN_PROGRESS"

    resolved_retry = resolve_investigation(
        db_session,
        inv.investigation_id,
        outcome="CONFIRMED_FRAUD",
        findings="Resolved cleanly after flush failure recovery.",
    )
    assert resolved_retry.status == "RESOLVED"
    assert resolved_retry.alert.status == "RESOLVED"


def test_start_investigation_explicit_none_unassigns_existing_analyst(db_session):
    """Passing assigned_to=None to start_investigation() explicitly clears a pre-existing analyst."""
    alert = _seed_alert(db_session, tx_id="TX-START-UNASSIGN-1")
    inv = create_investigation(db_session, alert_id=alert.alert_id, assigned_to="analyst_initial")
    assert inv.assigned_to == "analyst_initial"

    started = start_investigation(
        db_session,
        inv.investigation_id,
        assigned_to=None,
        note="Returned to unassigned triage queue.",
    )
    assert started.status == "IN_PROGRESS"
    assert started.assigned_to is None

    db_session.expire_all()
    persisted_inv = db_session.get(Investigation, inv.investigation_id)
    assert persisted_inv.status == "IN_PROGRESS"
    assert persisted_inv.assigned_to is None
    _, clean, _ = parse_investigation_findings(persisted_inv.findings)
    assert "Returned to unassigned triage queue." in (clean or "")


def test_list_investigations_status_and_outcome_filter_validation(db_session):
    """Status filter supports OPEN, IN_PROGRESS, RESOLVED, historical CLOSED, and rejects invalid values."""
    alert_open = _seed_alert(db_session, tx_id="TX-FILT-OPEN")
    alert_prog = _seed_alert(db_session, tx_id="TX-FILT-PROG")
    alert_res = _seed_alert(db_session, tx_id="TX-FILT-RES")
    alert_closed = _seed_alert(db_session, tx_id="TX-FILT-CLOSED")

    inv_open = create_investigation(db_session, alert_id=alert_open.alert_id, assigned_to="a1")

    inv_prog = create_investigation(db_session, alert_id=alert_prog.alert_id, assigned_to="a2")
    start_investigation(db_session, inv_prog.investigation_id)

    inv_res = create_investigation(db_session, alert_id=alert_res.alert_id, assigned_to="a3")
    start_investigation(db_session, inv_res.investigation_id)
    resolve_investigation(
        db_session,
        inv_res.investigation_id,
        outcome="CONFIRMED_FRAUD",
        findings="Confirmed in filter test.",
    )

    legacy_closed = Investigation(
        alert_id=alert_closed.alert_id,
        assigned_to="legacy_analyst",
        status="CLOSED",
        findings="Historical closed case.",
    )
    db_session.add(legacy_closed)
    db_session.commit()
    db_session.refresh(legacy_closed)

    assert [i.investigation_id for i in list_investigations(db_session, status="OPEN")] == [
        inv_open.investigation_id
    ]
    assert [i.investigation_id for i in list_investigations(db_session, status="IN_PROGRESS")] == [
        inv_prog.investigation_id
    ]
    assert [i.investigation_id for i in list_investigations(db_session, status="  in_progress ")] == [
        inv_prog.investigation_id
    ]
    assert [i.investigation_id for i in list_investigations(db_session, status="RESOLVED")] == [
        inv_res.investigation_id
    ]
    assert [i.investigation_id for i in list_investigations(db_session, status="CLOSED")] == [
        legacy_closed.investigation_id
    ]

    for invalid_status in ("INVALID", "ARCHIVED", "   "):
        with pytest.raises(InvestigationValidationError, match="Invalid investigation status"):
            list_investigations(db_session, status=invalid_status)

    with pytest.raises(InvestigationValidationError, match="Invalid investigation outcome"):
        list_investigations(db_session, outcome="INVALID_OUTCOME")




