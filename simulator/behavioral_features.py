from simulator.customer import CustomerProfile
from simulator.schemas import Transaction

def calculate_transaction_velocity(customer: CustomerProfile) -> int:
    """Return 1 when transaction frequency is unusually high."""

    return int(customer.transaction_count >= 3)
def calculate_behavioral_features(
    transaction: Transaction,
    customer: CustomerProfile,
) -> dict:
    new_device = int(
        transaction.device_id != customer.usual_device
    )

    unusual_location = int(
        transaction.location != customer.usual_location
    )

    high_velocity = calculate_transaction_velocity(customer)

    return {
        "new_device": new_device,
        "unusual_location": unusual_location,
        "high_velocity": high_velocity,
    }