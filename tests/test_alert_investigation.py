import pytest
from datetime import datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base
from backend.app.models import (
    Alert,
    Customer,
    Investigation,
    Transaction,
)


@pytest.fixture
def db_session():
    """Create an isolated in-memory database for relationship tests."""
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


@pytest.fixture
def stored_transaction(db_session):
    """Create a customer and transaction for alert tests."""
    customer = Customer(
        customer_id="REL-CUSTOMER-001",
    )

    transaction = Transaction(
        transaction_id="REL-TRANSACTION-001",
        customer_id="REL-CUSTOMER-001",
        amount=1500.0,
        merchant_category="retail",
        device_id="REL-DEVICE-001",
        location="Ujjain",
        timestamp=datetime(2026, 10, 27, 10, 30, 0),
        payment_method="credit_card",
        transaction_type="purchase",
        oldbalance_org=5000.0,
        newbalance_orig=3500.0,
        oldbalance_dest=1000.0,
        newbalance_dest=2500.0,
        step=1,
        fraud_prediction=1,
    )

    db_session.add(customer)
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)

    return transaction


def test_alert_can_be_created_for_transaction(
    db_session,
    stored_transaction,
):
    """Verify that an alert is associated with its transaction."""
    alert = Alert(
        transaction_id=stored_transaction.transaction_id,
        alert_type="FRAUD_SUSPECTED",
    )

    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    stored_alert = db_session.get(Alert, alert.alert_id)

    assert stored_alert is not None
    assert stored_alert.transaction_id == "REL-TRANSACTION-001"
    assert stored_alert.status == "OPEN"
    assert stored_alert.transaction.transaction_id == "REL-TRANSACTION-001"

    assert len(stored_alert.transaction.alerts) == 1


def test_investigation_can_be_associated_with_alert(
    db_session,
    stored_transaction,
):
    """Verify that an investigation is associated with its alert."""
    alert = Alert(
        transaction_id=stored_transaction.transaction_id,
        alert_type="FRAUD_SUSPECTED",
    )

    db_session.add(alert)
    db_session.flush()

    investigation = Investigation(
        alert_id=alert.alert_id,
        assigned_to="fraud_analyst",
        status="OPEN",
        findings="Pending review",
    )

    db_session.add(investigation)
    db_session.commit()
    db_session.refresh(investigation)

    stored_investigation = db_session.get(
        Investigation,
        investigation.investigation_id,
    )

    assert stored_investigation is not None
    assert stored_investigation.alert_id == alert.alert_id
    assert stored_investigation.assigned_to == "fraud_analyst"
    assert stored_investigation.status == "OPEN"
    assert stored_investigation.findings == "Pending review"

    assert stored_investigation.alert.alert_id == alert.alert_id
    assert stored_investigation.alert.investigation.investigation_id == (
        investigation.investigation_id
    )


def test_alert_can_exist_without_investigation(
    db_session,
    stored_transaction,
):
    """Verify that an alert does not require an investigation immediately."""
    alert = Alert(
        transaction_id=stored_transaction.transaction_id,
        alert_type="FRAUD_SUSPECTED",
    )

    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    assert alert.investigation is None


def test_investigation_requires_an_alert_id(db_session):
    """Verify that an investigation cannot omit its alert reference."""
    investigation = Investigation(
        assigned_to="fraud_analyst",
        status="OPEN",
    )

    db_session.add(investigation)

    with pytest.raises(Exception):
        db_session.commit()

    db_session.rollback()


def test_investigation_is_unique_per_alert(
    db_session,
    stored_transaction,
):
    """Verify that one alert cannot have two investigations."""
    alert = Alert(
        transaction_id=stored_transaction.transaction_id,
        alert_type="FRAUD_SUSPECTED",
    )

    db_session.add(alert)
    db_session.flush()

    first_investigation = Investigation(
        alert_id=alert.alert_id,
        assigned_to="analyst_one",
    )

    db_session.add(first_investigation)
    db_session.commit()

    second_investigation = Investigation(
        alert_id=alert.alert_id,
        assigned_to="analyst_two",
    )

    db_session.add(second_investigation)

    with pytest.raises(Exception):
        db_session.commit()

    db_session.rollback()

    investigations = db_session.scalars(
        select(Investigation).where(
            Investigation.alert_id == alert.alert_id
        )
    ).all()

    assert len(investigations) == 1