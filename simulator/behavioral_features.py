from datetime import datetime, timedelta

from simulator.customer import CustomerProfile
from simulator.schemas import Transaction


# Prototype rule; calibrate using historical transaction data.
VELOCITY_WINDOW_MINUTES = 5
VELOCITY_THRESHOLD = 3


def calculate_transaction_velocity(
    customer: CustomerProfile,
    current_timestamp: datetime,
) -> int:
    """
    Return 1 when at least VELOCITY_THRESHOLD transactions,
    including the current transaction, occur within the
    configured rolling time window.
    """

    window_start = current_timestamp - timedelta(
        minutes=VELOCITY_WINDOW_MINUTES
    )

    recent_timestamps = [
        timestamp
        for timestamp in customer.transaction_timestamps
        if window_start <= timestamp <= current_timestamp
    ]

    # Include the current transaction exactly once.
    current_transaction_count = sum(
        timestamp == current_timestamp
        for timestamp in recent_timestamps
    )

    if current_transaction_count == 0:
        recent_timestamps.append(current_timestamp)

    return int(len(recent_timestamps) >= VELOCITY_THRESHOLD)


def calculate_behavioral_features(
    transaction: Transaction,
    customer: CustomerProfile,
) -> dict:
    """Calculate behavioral indicators for a transaction."""

    new_device = int(
        transaction.device_id != customer.usual_device
    )

    unusual_location = int(
        transaction.location != customer.usual_location
    )

    high_velocity = calculate_transaction_velocity(
        customer=customer,
        current_timestamp=transaction.timestamp,
    )

    return {
        "new_device": new_device,
        "unusual_location": unusual_location,
        "high_velocity": high_velocity,
    }