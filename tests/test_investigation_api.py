from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base, get_db
from backend.app.main import app
from backend.app.models import Alert, Customer, Transaction as TransactionModel
from backend.app.models import Investigation
from backend.app.services.risk_service import score_submitted_transaction
from simulator.schemas import Transaction

from tests.test_persistence import mock_model_predictions


@pytest.fixture
def test_db(monkeypatch):
    """Create an isolated in-memory SQLite database for each test."""
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

    monkeypatch.setattr(
        "backend.app.services.risk_service.SessionLocal",
        TestingSessionLocal,
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setitem(
        app.dependency_overrides,
        get_db,
        override_get_db,
    )

    try:
        yield TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def persisted_alert(test_db):
    """Create a customer, transaction, and alert in the test database."""
    with test_db() as db:
        customer = Customer(customer_id="INV-TEST-CUSTOMER")
        db.add(customer)
        db.flush()

        transaction = TransactionModel(
            transaction_id="INV-TEST-TRANSACTION",
            customer_id=customer.customer_id,
            amount=1500.0,
            merchant_category="retail",
            device_id="INV-TEST-DEVICE",
            location="Ujjain",
            timestamp=datetime(2026, 10, 25, 10, 30, 0),
            payment_method="credit_card",
            transaction_type="purchase",
            oldbalance_org=5000.0,
            newbalance_orig=3500.0,
            oldbalance_dest=1000.0,
            newbalance_dest=2500.0,
            step=1,
            fraud_prediction=0,
        )
        db.add(transaction)
        db.flush()

        alert = Alert(
            transaction_id=transaction.transaction_id,
            alert_type="FRAUD_SUSPECTED",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        return alert.alert_id


def test_create_investigation_for_existing_alert(
    client,
    persisted_alert,
    test_db,
):
    """Creating an investigation for an existing alert returns HTTP 201."""
    response = client.post(
        "/api/v1/investigations",
        json={
            "alert_id": persisted_alert,
            "assigned_to": "fraud_analyst_01",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["investigation_id"] > 0
    assert data["alert_id"] == persisted_alert
    assert data["assigned_to"] == "fraud_analyst_01"
    assert data["status"] == "OPEN"
    assert data["findings"] is None
    assert "created_at" in data
    assert "updated_at" in data

    with test_db() as db:
        saved = db.get(Investigation, data["investigation_id"])
        assert saved is not None
        assert saved.alert_id == persisted_alert


def test_create_investigation_for_missing_alert_returns_404(client, test_db):
    """Creating an investigation for a missing alert returns HTTP 404."""
    response = client.post(
        "/api/v1/investigations",
        json={
            "alert_id": 999999,
            "assigned_to": "fraud_analyst_01",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Alert not found."


def test_duplicate_investigation_returns_409(
    client,
    persisted_alert,
):
    """Only one investigation may exist for an alert."""
    payload = {
        "alert_id": persisted_alert,
        "assigned_to": "fraud_analyst_01",
    }

    first_response = client.post(
        "/api/v1/investigations",
        json=payload,
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/investigations",
        json=payload,
    )

    assert second_response.status_code == 409


def test_get_investigations(
    client,
    persisted_alert,
):
    """The list endpoint returns saved investigations."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    )
    assert created.status_code == 201

    response = client.get("/api/v1/investigations")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["alert_id"] == persisted_alert


def test_filter_investigations_by_alert_id(
    client,
    persisted_alert,
):
    """Investigations can be filtered by alert ID."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    )
    assert created.status_code == 201

    response = client.get(
        "/api/v1/investigations",
        params={"alert_id": persisted_alert},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["alert_id"] == persisted_alert

    missing_response = client.get(
        "/api/v1/investigations",
        params={"alert_id": 999999},
    )

    assert missing_response.status_code == 200
    assert missing_response.json() == []


def test_filter_investigations_by_status_and_assignee(
    client,
    persisted_alert,
):
    """Investigations can be filtered by status and assignee."""
    created = client.post(
        "/api/v1/investigations",
        json={
            "alert_id": persisted_alert,
            "assigned_to": "fraud_analyst_01",
        },
    )
    assert created.status_code == 201

    status_response = client.get(
        "/api/v1/investigations",
        params={"status": "OPEN"},
    )

    assert status_response.status_code == 200
    assert len(status_response.json()) == 1

    assignee_response = client.get(
        "/api/v1/investigations",
        params={"assigned_to": "fraud_analyst_01"},
    )

    assert assignee_response.status_code == 200
    assert len(assignee_response.json()) == 1

    missing_assignee_response = client.get(
        "/api/v1/investigations",
        params={"assigned_to": "unknown_analyst"},
    )

    assert missing_assignee_response.status_code == 200
    assert missing_assignee_response.json() == []


def test_get_investigation_by_id(
    client,
    persisted_alert,
):
    """A saved investigation can be retrieved by ID."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    )
    assert created.status_code == 201

    investigation_id = created.json()["investigation_id"]

    response = client.get(
        f"/api/v1/investigations/{investigation_id}"
    )

    assert response.status_code == 200
    assert response.json()["investigation_id"] == investigation_id
    assert response.json()["alert_id"] == persisted_alert


def test_get_missing_investigation_returns_404(client, test_db):
    """A nonexistent investigation returns HTTP 404."""
    response = client.get("/api/v1/investigations/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Investigation not found."


def test_update_investigation_status_and_findings(
    client,
    persisted_alert,
):
    """Status and findings can be updated."""
    created = client.post(
        "/api/v1/investigations",
        json={
            "alert_id": persisted_alert,
            "assigned_to": "fraud_analyst_01",
        },
    )
    assert created.status_code == 201

    investigation_id = created.json()["investigation_id"]

    response = client.patch(
        f"/api/v1/investigations/{investigation_id}",
        json={
            "status": "IN_PROGRESS",
            "findings": "Further verification is required.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "IN_PROGRESS"
    assert data["findings"] == "Further verification is required."
    assert data["assigned_to"] == "fraud_analyst_01"


def test_update_investigation_assignee(
    client,
    persisted_alert,
):
    """The assigned analyst can be updated."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    )
    assert created.status_code == 201

    investigation_id = created.json()["investigation_id"]

    response = client.patch(
        f"/api/v1/investigations/{investigation_id}",
        json={"assigned_to": "fraud_analyst_02"},
    )

    assert response.status_code == 200
    assert response.json()["assigned_to"] == "fraud_analyst_02"


def test_update_missing_investigation_returns_404(client, test_db):
    """Updating a nonexistent investigation returns HTTP 404."""
    response = client.patch(
        "/api/v1/investigations/999999",
        json={"status": "IN_PROGRESS"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Investigation not found."


def test_update_investigation_with_empty_body_returns_422(
    client,
    persisted_alert,
):
    """An empty update body is rejected."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    )
    assert created.status_code == 201

    investigation_id = created.json()["investigation_id"]

    response = client.patch(
        f"/api/v1/investigations/{investigation_id}",
        json={},
    )

    assert response.status_code == 422


def test_investigation_request_validation(client):
    """Invalid request payloads and query parameters return HTTP 422."""
    invalid_alert_response = client.post(
        "/api/v1/investigations",
        json={"alert_id": 0},
    )
    assert invalid_alert_response.status_code == 422

    missing_alert_response = client.post(
        "/api/v1/investigations",
        json={},
    )
    assert missing_alert_response.status_code == 422

    invalid_limit_response = client.get(
        "/api/v1/investigations",
        params={"limit": 101},
    )
    assert invalid_limit_response.status_code == 422

    invalid_offset_response = client.get(
        "/api/v1/investigations",
        params={"offset": -1},
    )
    assert invalid_offset_response.status_code == 422

    invalid_alert_id_response = client.get(
        "/api/v1/investigations",
        params={"alert_id": 0},
    )
    assert invalid_alert_id_response.status_code == 422


def test_investigation_pagination(
    client,
    test_db,
):
    """Investigation listing supports limit and offset."""
    with test_db() as db:
        customer = Customer(customer_id="INV-PAGE-CUSTOMER")
        db.add(customer)
        db.flush()

        transaction = TransactionModel(
            transaction_id="INV-PAGE-TRANSACTION",
            customer_id=customer.customer_id,
            amount=1000.0,
            merchant_category="retail",
            device_id="INV-PAGE-DEVICE",
            location="Ujjain",
            timestamp=datetime(2026, 10, 25, 10, 30, 0),
            payment_method="credit_card",
            transaction_type="purchase",
            oldbalance_org=5000.0,
            newbalance_orig=4000.0,
            oldbalance_dest=1000.0,
            newbalance_dest=2000.0,
            step=1,
            fraud_prediction=0,
        )
        db.add(transaction)
        db.flush()

        first_alert = Alert(
            transaction_id=transaction.transaction_id,
            alert_type="FRAUD_SUSPECTED",
        )
        second_alert = Alert(
            transaction_id=transaction.transaction_id,
            alert_type="HIGH_RISK",
        )
        db.add_all([first_alert, second_alert])
        db.flush()

        db.add_all(
            [
                Investigation(alert_id=first_alert.alert_id),
                Investigation(alert_id=second_alert.alert_id),
            ]
        )
        db.commit()

    first_page = client.get(
        "/api/v1/investigations",
        params={"limit": 1, "offset": 0},
    )

    assert first_page.status_code == 200
    assert len(first_page.json()) == 1

    beyond_page = client.get(
        "/api/v1/investigations",
        params={"limit": 1, "offset": 2},
    )

    assert beyond_page.status_code == 200
    assert beyond_page.json() == []


# ---------------------------------------------------------------------------
# Step 9.3: Investigation Domain Service API Integration Tests
# ---------------------------------------------------------------------------

def _seed_extra_alert(test_db, suffix: str) -> int:
    """Create a standalone Customer, Transaction, and OPEN Alert returning alert_id."""
    with test_db() as db:
        customer = Customer(customer_id=f"INV-93-CUST-{suffix}")
        db.add(customer)
        db.flush()

        tx = TransactionModel(
            transaction_id=f"INV-93-TX-{suffix}",
            customer_id=customer.customer_id,
            amount=42000.0,
            merchant_category="electronics",
            device_id=f"DEV-93-{suffix}",
            location="Mumbai",
            timestamp=datetime(2026, 11, 20, 12, 0, 0),
            payment_method="credit_card",
            transaction_type="purchase",
            oldbalance_org=100000.0,
            newbalance_orig=58000.0,
            oldbalance_dest=10000.0,
            newbalance_dest=52000.0,
            step=1,
            fraud_prediction=1,
        )
        db.add(tx)
        db.flush()

        alert = Alert(
            transaction_id=tx.transaction_id,
            alert_type="ML_FRAUD_DETECTED",
            status="OPEN",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert.alert_id


def test_create_investigation_with_initial_note_and_assignee_validation(
    client,
    persisted_alert,
):
    """POST /api/v1/investigations persists timestamped initial_note and enforces assignee rules."""
    ws_resp = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert, "assigned_to": "   "},
    )
    assert ws_resp.status_code == 422

    too_long_resp = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert, "assigned_to": "a" * 101},
    )
    assert too_long_resp.status_code == 422

    created = client.post(
        "/api/v1/investigations",
        json={
            "alert_id": persisted_alert,
            "assigned_to": "  lead_analyst  ",
            "initial_note": "Escalated from real-time fraud stream.",
        },
    )
    assert created.status_code == 201
    data = created.json()
    assert data["assigned_to"] == "lead_analyst"
    assert data["status"] == "OPEN"
    assert data["outcome"] is None
    assert len(data["notes"]) == 1
    assert data["notes"][0]["author"] == "lead_analyst"
    assert data["notes"][0]["content"] == "Escalated from real-time fraud stream."
    assert data["notes"][0]["timestamp"] is not None


def test_list_investigations_status_outcome_filters_and_context(client, test_db):
    """GET /api/v1/investigations validates status/outcome filters, supports CLOSED, and loads optional context."""
    alert_open = _seed_extra_alert(test_db, "LIST-OPEN")
    alert_prog = _seed_extra_alert(test_db, "LIST-PROG")
    alert_res = _seed_extra_alert(test_db, "LIST-RES")
    alert_closed = _seed_extra_alert(test_db, "LIST-CLOSED")

    inv_open = client.post(
        "/api/v1/investigations",
        json={"alert_id": alert_open, "assigned_to": "analyst_open"},
    ).json()

    inv_prog = client.post(
        "/api/v1/investigations",
        json={"alert_id": alert_prog, "assigned_to": "analyst_prog"},
    ).json()
    assert (
        client.post(f"/api/v1/investigations/{inv_prog['investigation_id']}/start").status_code
        == 200
    )

    inv_res = client.post(
        "/api/v1/investigations",
        json={"alert_id": alert_res, "assigned_to": "analyst_res"},
    ).json()
    assert (
        client.post(f"/api/v1/investigations/{inv_res['investigation_id']}/start").status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/investigations/{inv_res['investigation_id']}/resolve",
            json={"outcome": "CONFIRMED_FRAUD", "findings": "Verified fraud ring."},
        ).status_code
        == 200
    )

    with test_db() as db:
        legacy = Investigation(
            alert_id=alert_closed,
            assigned_to="legacy_analyst",
            status="CLOSED",
            findings="Historical Phase 6 closed record.",
        )
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        legacy_id = legacy.investigation_id

    for filter_status, expected_id in [
        ("OPEN", inv_open["investigation_id"]),
        ("IN_PROGRESS", inv_prog["investigation_id"]),
        ("RESOLVED", inv_res["investigation_id"]),
        ("CLOSED", legacy_id),
    ]:
        resp = client.get("/api/v1/investigations", params={"status": filter_status})
        assert resp.status_code == 200
        items = resp.json()
        assert [item["investigation_id"] for item in items] == [expected_id]
        assert items[0]["alert"] is None

    # Invalid status and whitespace status must return 422, not 200 []
    invalid_status_resp = client.get("/api/v1/investigations", params={"status": "INVALID"})
    assert invalid_status_resp.status_code == 422

    blank_status_resp = client.get("/api/v1/investigations", params={"status": "   "})
    assert blank_status_resp.status_code == 422

    # Outcome filter & optional include_context
    outcome_resp = client.get(
        "/api/v1/investigations",
        params={"outcome": "CONFIRMED_FRAUD", "include_context": "true"},
    )
    assert outcome_resp.status_code == 200
    outcome_items = outcome_resp.json()
    assert [item["investigation_id"] for item in outcome_items] == [inv_res["investigation_id"]]
    assert outcome_items[0]["alert"] is not None
    assert outcome_items[0]["alert"]["status"] == "RESOLVED"
    assert outcome_items[0]["alert"]["transaction"]["transaction_id"] == "INV-93-TX-LIST-RES"

    invalid_outcome_resp = client.get("/api/v1/investigations", params={"outcome": "INVALID"})
    assert invalid_outcome_resp.status_code == 422


def test_get_investigation_by_id_context_toggle(client, persisted_alert):
    """GET /api/v1/investigations/{id} returns linked alert/transaction by default and honors include_context=false."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    ).json()
    inv_id = created["investigation_id"]

    with_ctx = client.get(f"/api/v1/investigations/{inv_id}")
    assert with_ctx.status_code == 200
    ctx_data = with_ctx.json()
    assert ctx_data["alert"] is not None
    assert ctx_data["alert"]["alert_id"] == persisted_alert
    assert ctx_data["alert"]["transaction"]["transaction_id"] == "INV-TEST-TRANSACTION"

    without_ctx = client.get(f"/api/v1/investigations/{inv_id}", params={"include_context": "false"})
    assert without_ctx.status_code == 200
    assert without_ctx.json()["alert"] is None


def test_assign_investigation_endpoint_lifecycle_and_validation(client, persisted_alert):
    """POST /api/v1/investigations/{id}/assign assigns, reassigns, unassigns, and rejects invalid requests."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert},
    ).json()
    inv_id = created["investigation_id"]

    assigned = client.post(
        f"/api/v1/investigations/{inv_id}/assign",
        json={"assigned_to": "  analyst_alpha  ", "note": "Picked up for review."},
    )
    assert assigned.status_code == 200
    assigned_data = assigned.json()
    assert assigned_data["assigned_to"] == "analyst_alpha"
    assert len(assigned_data["notes"]) == 1
    assert assigned_data["notes"][0]["content"] == "Picked up for review."

    unassigned = client.post(
        f"/api/v1/investigations/{inv_id}/assign",
        json={"assigned_to": None},
    )
    assert unassigned.status_code == 200
    assert unassigned.json()["assigned_to"] is None

    # Validation checks
    assert client.post(f"/api/v1/investigations/{inv_id}/assign", json={}).status_code == 422
    assert (
        client.post(f"/api/v1/investigations/{inv_id}/assign", json={"assigned_to": "   "}).status_code
        == 422
    )
    assert (
        client.post(f"/api/v1/investigations/{inv_id}/assign", json={"assigned_to": "x" * 101}).status_code
        == 422
    )
    assert (
        client.post("/api/v1/investigations/999999/assign", json={"assigned_to": "analyst_x"}).status_code
        == 404
    )

    # Terminal resolved case cannot be reassigned
    client.post(f"/api/v1/investigations/{inv_id}/start")
    client.post(
        f"/api/v1/investigations/{inv_id}/resolve",
        json={"outcome": "LEGITIMATE", "findings": "Cleared by customer."},
    )
    assert (
        client.post(f"/api/v1/investigations/{inv_id}/assign", json={"assigned_to": "analyst_y"}).status_code
        == 422
    )


def test_start_investigation_endpoint_preserves_and_clears_assignee(client, test_db):
    """POST /api/v1/investigations/{id}/start preserves omitted assignee, allows explicit null, and enforces state."""
    alert_1 = _seed_extra_alert(test_db, "START-1")
    alert_2 = _seed_extra_alert(test_db, "START-2")

    inv_1 = client.post(
        "/api/v1/investigations",
        json={"alert_id": alert_1, "assigned_to": "analyst_keep"},
    ).json()
    inv_2 = client.post(
        "/api/v1/investigations",
        json={"alert_id": alert_2, "assigned_to": "analyst_clear"},
    ).json()

    # Empty / omitted body preserves existing assignment
    started_1 = client.post(f"/api/v1/investigations/{inv_1['investigation_id']}/start")
    assert started_1.status_code == 200
    assert started_1.json()["status"] == "IN_PROGRESS"
    assert started_1.json()["assigned_to"] == "analyst_keep"

    # Re-starting an IN_PROGRESS investigation returns 422
    assert client.post(f"/api/v1/investigations/{inv_1['investigation_id']}/start").status_code == 422

    # Explicit null unassigns existing analyst while transitioning OPEN -> IN_PROGRESS
    started_2 = client.post(
        f"/api/v1/investigations/{inv_2['investigation_id']}/start",
        json={"assigned_to": None, "note": "Returned to triage pool."},
    )
    assert started_2.status_code == 200
    assert started_2.json()["status"] == "IN_PROGRESS"
    assert started_2.json()["assigned_to"] is None
    assert started_2.json()["notes"][0]["content"] == "Returned to triage pool."

    assert client.post("/api/v1/investigations/999999/start").status_code == 404


def test_add_investigation_note_endpoint_appends_and_validates(client, persisted_alert):
    """POST /api/v1/investigations/{id}/notes appends timestamped notes cleanly."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert, "assigned_to": "analyst_notes"},
    ).json()
    inv_id = created["investigation_id"]
    client.post(f"/api/v1/investigations/{inv_id}/start")

    n1 = client.post(
        f"/api/v1/investigations/{inv_id}/notes",
        json={"note": "Checked device fingerprint.", "author": "analyst_notes"},
    )
    assert n1.status_code == 200
    assert len(n1.json()["notes"]) == 1

    n2 = client.post(
        f"/api/v1/investigations/{inv_id}/notes",
        json={"note": "Verified IP velocity spike."},
    )
    assert n2.status_code == 200
    n2_data = n2.json()
    assert [n["content"] for n in n2_data["notes"]] == [
        "Checked device fingerprint.",
        "Verified IP velocity spike.",
    ]
    assert n2_data["notes"][1]["author"] == "analyst_notes"

    assert (
        client.post(f"/api/v1/investigations/{inv_id}/notes", json={"note": "   "}).status_code == 422
    )
    assert (
        client.post("/api/v1/investigations/999999/notes", json={"note": "Missing case"}).status_code
        == 404
    )

    client.post(
        f"/api/v1/investigations/{inv_id}/resolve",
        json={"outcome": "CONFIRMED_FRAUD", "findings": "Final fraud determination."},
    )
    assert (
        client.post(f"/api/v1/investigations/{inv_id}/notes", json={"note": "Post-resolve note"}).status_code
        == 422
    )


def test_resolve_investigation_endpoint_syncs_alert_for_both_outcomes(client, test_db):
    """POST /api/v1/investigations/{id}/resolve syncs linked alert status for both outcomes."""
    alert_fraud = _seed_extra_alert(test_db, "RES-FRAUD")
    alert_legit = _seed_extra_alert(test_db, "RES-LEGIT")

    inv_fraud = client.post(
        "/api/v1/investigations",
        json={"alert_id": alert_fraud, "assigned_to": "analyst_f"},
    ).json()
    client.post(f"/api/v1/investigations/{inv_fraud['investigation_id']}/start")

    res_fraud = client.post(
        f"/api/v1/investigations/{inv_fraud['investigation_id']}/resolve",
        json={
            "outcome": "CONFIRMED_FRAUD",
            "findings": "Account takeover confirmed.",
        },
    )
    assert res_fraud.status_code == 200
    fraud_data = res_fraud.json()
    assert fraud_data["status"] == "RESOLVED"
    assert fraud_data["outcome"] == "CONFIRMED_FRAUD"
    assert fraud_data["assigned_to"] == "analyst_f"
    assert fraud_data["alert"]["status"] == "RESOLVED"

    # Second investigation uses an existing logged note without extra resolution findings
    inv_legit = client.post(
        "/api/v1/investigations",
        json={"alert_id": alert_legit, "assigned_to": "analyst_l"},
    ).json()
    client.post(f"/api/v1/investigations/{inv_legit['investigation_id']}/start")
    client.post(
        f"/api/v1/investigations/{inv_legit['investigation_id']}/notes",
        json={"note": "Cardholder confirmed legitimate travel spend."},
    )

    res_legit = client.post(
        f"/api/v1/investigations/{inv_legit['investigation_id']}/resolve",
        json={"outcome": "LEGITIMATE"},
    )
    assert res_legit.status_code == 200
    legit_data = res_legit.json()
    assert legit_data["status"] == "RESOLVED"
    assert legit_data["outcome"] == "LEGITIMATE"
    assert legit_data["alert"]["status"] == "DISMISSED"
    assert "Cardholder confirmed legitimate travel spend." in legit_data["findings"]

    with test_db() as db:
        assert db.get(Alert, alert_fraud).status == "RESOLVED"
        assert db.get(Alert, alert_legit).status == "DISMISSED"


def test_resolve_investigation_endpoint_validation_and_rollback(client, test_db, monkeypatch):
    """Resolution endpoint rejects invalid states/outcomes/missing findings and rolls back on failure."""
    alert_id = _seed_extra_alert(test_db, "RES-ERR")
    inv = client.post(
        "/api/v1/investigations",
        json={"alert_id": alert_id, "assigned_to": "analyst_err"},
    ).json()
    inv_id = inv["investigation_id"]

    # Direct resolve from OPEN -> 422
    assert (
        client.post(
            f"/api/v1/investigations/{inv_id}/resolve",
            json={"outcome": "CONFIRMED_FRAUD", "findings": "Skipping IN_PROGRESS."},
        ).status_code
        == 422
    )

    client.post(f"/api/v1/investigations/{inv_id}/start")

    # Missing findings and invalid outcome -> 422
    assert (
        client.post(
            f"/api/v1/investigations/{inv_id}/resolve",
            json={"outcome": "CONFIRMED_FRAUD"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/investigations/{inv_id}/resolve",
            json={"outcome": "INVALID_OUTCOME", "findings": "Bad outcome."},
        ).status_code
        == 422
    )

    # Alert sync runtime failure -> 500 with atomic rollback
    def broken_sync(db, investigation, outcome):
        raise RuntimeError("Simulated sync failure in API")

    with monkeypatch.context() as mp:
        mp.setattr(
            "backend.app.services.investigation_service._sync_alert_status",
            broken_sync,
        )
        sync_err_resp = client.post(
            f"/api/v1/investigations/{inv_id}/resolve",
            json={"outcome": "CONFIRMED_FRAUD", "findings": "Should roll back cleanly."},
        )
        assert sync_err_resp.status_code == 500

    with test_db() as db:
        persisted_inv = db.get(Investigation, inv_id)
        persisted_alert = db.get(Alert, alert_id)
        assert persisted_inv.status == "IN_PROGRESS"
        assert persisted_alert.status == "OPEN"

    # Missing linked alert during resolution -> 404 and investigation unchanged
    with test_db() as db:
        db.execute(delete(Alert).where(Alert.alert_id == alert_id))
        db.commit()

    missing_alert_resp = client.post(
        f"/api/v1/investigations/{inv_id}/resolve",
        json={"outcome": "LEGITIMATE", "findings": "Parent alert vanished."},
    )
    assert missing_alert_resp.status_code == 404

    with test_db() as db:
        assert db.get(Investigation, inv_id).status == "IN_PROGRESS"


def test_patch_update_investigation_preserves_history_and_enforces_lifecycle(
    client,
    persisted_alert,
    test_db,
):
    """PATCH /api/v1/investigations/{id} integrates lifecycle rules, note/findings history, and alert sync."""
    created = client.post(
        "/api/v1/investigations",
        json={"alert_id": persisted_alert, "assigned_to": "patch_analyst"},
    ).json()
    inv_id = created["investigation_id"]

    # Transition to IN_PROGRESS with a timestamped note
    started = client.patch(
        f"/api/v1/investigations/{inv_id}",
        json={"status": "IN_PROGRESS", "note": "Initial patch check."},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "IN_PROGRESS"

    # Partial findings update preserves historical timestamped note
    updated = client.patch(
        f"/api/v1/investigations/{inv_id}",
        json={"findings": "Consolidated merchant summary."},
    )
    assert updated.status_code == 200
    updated_data = updated.json()
    assert "Consolidated merchant summary." in updated_data["findings"]
    assert any(n["content"] == "Initial patch check." for n in updated_data["notes"])

    # Invalid PATCH combinations -> 422
    assert (
        client.patch(
            f"/api/v1/investigations/{inv_id}",
            json={"outcome": "CONFIRMED_FRAUD"},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/investigations/{inv_id}",
            json={"status": "RESOLVED"},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/investigations/{inv_id}",
            json={"status": None},
        ).status_code
        == 422
    )

    # Valid resolution via PATCH atomically updates Alert
    resolved = client.patch(
        f"/api/v1/investigations/{inv_id}",
        json={
            "status": "RESOLVED",
            "outcome": "LEGITIMATE",
            "note": "Verified legitimate cardholder activity.",
        },
    )
    assert resolved.status_code == 200
    resolved_data = resolved.json()
    assert resolved_data["status"] == "RESOLVED"
    assert resolved_data["outcome"] == "LEGITIMATE"
    assert resolved_data["alert"]["status"] == "DISMISSED"

    with test_db() as db:
        assert db.get(Alert, persisted_alert).status == "DISMISSED"

    # Terminal RESOLVED investigation rejects further PATCH mutations
    assert (
        client.patch(
            f"/api/v1/investigations/{inv_id}",
            json={"findings": "Late edit"},
        ).status_code
        == 422
    )