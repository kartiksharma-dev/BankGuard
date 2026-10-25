
from datetime import datetime
from unittest.mock import patch

from pydantic import ValidationError

from simulator.customer import CustomerProfile
from simulator.generator import create_customer, generate_transaction
from simulator.pipeline import score_transaction
from simulator.scenarios import TransactionScenario
from simulator.schemas import Transaction


def test_normal_transaction():
    customer = create_customer("C1001")

    transaction = generate_transaction(
        scenario=TransactionScenario.NORMAL,
        customer=customer,
    )

    assert transaction.customer_id == "C1001"
    assert transaction.amount > 0
    assert transaction.device_id == customer.usual_device
    assert transaction.location == customer.usual_location

    print("PASS: Normal transaction")


def test_high_amount():
    customer = create_customer("C1002")

    transaction = generate_transaction(
        scenario=TransactionScenario.HIGH_AMOUNT,
        customer=customer,
    )

    assert transaction.amount >= 50000

    print("PASS: High amount transaction")


def test_new_device():
    customer = create_customer("C1003")

    transaction = generate_transaction(
        scenario=TransactionScenario.NEW_DEVICE,
        customer=customer,
    )

    assert transaction.device_id != customer.usual_device
    assert transaction.device_id.startswith("NEW")

    print("PASS: New device transaction")


def test_unusual_location():
    customer = create_customer("C1004")

    transaction = generate_transaction(
        scenario=TransactionScenario.UNUSUAL_LOCATION,
        customer=customer,
    )

    assert transaction.location != customer.usual_location

    print("PASS: Unusual location transaction")


def test_high_velocity():
    customer = create_customer("C1005")

    first_transaction = generate_transaction(
        scenario=TransactionScenario.NORMAL,
        customer=customer,
    )

    second_transaction = generate_transaction(
        scenario=TransactionScenario.HIGH_VELOCITY,
        customer=customer,
        previous_timestamp=first_transaction.timestamp,
    )

    time_difference = (
        second_transaction.timestamp - first_transaction.timestamp
    ).total_seconds()

    assert 1 <= time_difference <= 10

    print("PASS: High velocity transaction")


def test_customer_history():
    customer = create_customer("C1006")

    generate_transaction(
        scenario=TransactionScenario.NORMAL,
        customer=customer,
    )

    generate_transaction(
        scenario=TransactionScenario.NORMAL,
        customer=customer,
    )

    assert customer.transaction_count == 2
    assert len(customer.transaction_history) == 2

    print("PASS: Customer history")


def test_invalid_amount():
    try:
        Transaction(
            transaction_id="TXTEST",
            customer_id="C1007",
            amount=-100,
            merchant_category="ELECTRONICS",
            device_id="D100",
            location="Mumbai",
            timestamp=datetime.now(),
            payment_method="CARD",
        )

        assert False, "Negative amount should fail validation"

    except ValidationError:
        print("PASS: Invalid amount rejected")


def test_high_velocity_pipeline():
    with patch(
        "simulator.pipeline.predict_fraud",
        return_value={"fraud_prediction": 1},
    ):
        result = score_transaction(
            scenario=TransactionScenario.HIGH_VELOCITY
        )

    transaction = result["transaction"]
    behavioral_features = result["behavioral_features"]

    # Verify transaction details.
    assert transaction.transaction_id
    assert transaction.customer_id
    assert transaction.amount > 0

    # Verify the simulated model prediction is returned.
    assert result["fraud_prediction"] == 1

    # Verify behavioral detection.
    assert behavioral_features["high_velocity"] == 1
    assert behavioral_features["new_device"] == 0
    assert behavioral_features["unusual_location"] == 0

    print("PASS: High velocity pipeline")
