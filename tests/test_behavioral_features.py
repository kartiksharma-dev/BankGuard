from datetime import datetime, timedelta

from simulator.behavioral_features import (
    calculate_transaction_velocity,
)
from simulator.customer import CustomerProfile


def make_customer():
    return CustomerProfile(
        customer_id="CTEST001",
        usual_device="D101",
        usual_location="Mumbai",
    )


def test_high_velocity_with_three_transactions_in_window():
    customer = make_customer()
    now = datetime(2026, 10, 25, 12, 0, 0)

    customer.transaction_timestamps = [
        now - timedelta(minutes=4),
        now - timedelta(minutes=2),
    ]

    assert calculate_transaction_velocity(customer, now) == 1


def test_no_high_velocity_with_insufficient_transactions():
    customer = make_customer()
    now = datetime(2026, 10, 25, 12, 0, 0)

    customer.transaction_timestamps = [
        now - timedelta(minutes=2),
    ]

    assert calculate_transaction_velocity(customer, now) == 0


def test_old_transactions_outside_window_are_ignored():
    customer = make_customer()
    now = datetime(2026, 10, 25, 12, 0, 0)

    customer.transaction_timestamps = [
        now - timedelta(minutes=10),
        now - timedelta(minutes=8),
    ]

    assert calculate_transaction_velocity(customer, now) == 0


def test_transaction_exactly_at_window_boundary_is_counted():
    customer = make_customer()
    now = datetime(2026, 10, 25, 12, 0, 0)

    customer.transaction_timestamps = [
        now - timedelta(minutes=5),
        now - timedelta(minutes=4),
    ]

    assert calculate_transaction_velocity(customer, now) == 1


def test_future_transactions_are_ignored():
    customer = make_customer()
    now = datetime(2026, 10, 25, 12, 0, 0)

    customer.transaction_timestamps = [
        now + timedelta(minutes=1),
        now + timedelta(minutes=2),
    ]

    assert calculate_transaction_velocity(customer, now) == 0