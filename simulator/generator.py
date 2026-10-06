import random
import uuid
from datetime import datetime, timedelta

from simulator.customer import CustomerProfile, DestinationAccount
from simulator.schemas import Transaction
from simulator.scenarios import TransactionScenario


MERCHANT_CATEGORIES = [
    "GROCERY",
    "ELECTRONICS",
    "RESTAURANT",
    "TRAVEL",
    "SHOPPING",
    "FUEL",
]

LOCATIONS = [
    "Mumbai",
    "Delhi",
    "Bangalore",
    "Pune",
    "Hyderabad",
    "Chennai",
]

PAYMENT_METHODS = [
    "CARD",
    "UPI",
    "NET_BANKING",
]

TRANSACTION_TYPES = [
    "CASH_IN",
    "CASH_OUT",
    "DEBIT",
    "PAYMENT",
    "TRANSFER",
]


def create_customer(customer_id: str | None = None) -> CustomerProfile:
    """Create a new customer profile."""

    customer_id = customer_id or f"C{random.randint(1000, 9999)}"

    return CustomerProfile(
        customer_id=customer_id,
        usual_device=f"D{random.randint(100, 999)}",
        usual_location=random.choice(LOCATIONS),
    )


def generate_transaction(
    scenario: TransactionScenario = TransactionScenario.NORMAL,
    customer: CustomerProfile | None = None,
    destination: DestinationAccount | None = None,
    previous_timestamp: datetime | None = None,
) -> Transaction:
    """Generate a transaction based on customer behavior and scenario."""

    # Create customer if one was not provided
    if customer is None:
        customer = create_customer()

    # Create destination account if one was not provided
    if destination is None:
        destination = DestinationAccount(
            account_id=f"DST{random.randint(1000, 9999)}"
        )

    
    # Customer's normal behavior
    

    device_id = customer.usual_device
    location = customer.usual_location
    timestamp = datetime.now()

    
    # Account balances BEFORE transaction
    

    oldbalance_org = customer.account_balance
    oldbalance_dest = destination.balance

    
    # Generate transaction amount
    

    amount = round(random.uniform(100, 5000), 2)

    
    # Scenario-specific behavior
    

    if scenario == TransactionScenario.HIGH_AMOUNT:
        amount = round(random.uniform(50000, 100000), 2)

    elif scenario == TransactionScenario.NEW_DEVICE:
        device_id = f"NEW{random.randint(1000, 9999)}"

    elif scenario == TransactionScenario.UNUSUAL_LOCATION:
        unusual_locations = [
            location_name
            for location_name in LOCATIONS
            if location_name != customer.usual_location
        ]

        location = random.choice(unusual_locations)

    elif scenario == TransactionScenario.HIGH_VELOCITY:
        if previous_timestamp:
            timestamp = previous_timestamp + timedelta(
                seconds=random.randint(1, 10)
            )

    
    # Prevent transaction from exceeding origin balance
    

    if amount > oldbalance_org:
        amount = oldbalance_org

    
    # Calculate balances AFTER transaction


    newbalance_orig = oldbalance_org - amount
    newbalance_dest = oldbalance_dest + amount

    
    # Create validated transaction
    

    transaction = Transaction(
        transaction_id=f"TX{uuid.uuid4().hex[:8].upper()}",
        customer_id=customer.customer_id,
        amount=amount,
        merchant_category=random.choice(MERCHANT_CATEGORIES),
        device_id=device_id,
        location=location,
        timestamp=timestamp,
        payment_method=random.choice(PAYMENT_METHODS),

        oldbalance_org=oldbalance_org,
        newbalance_orig=newbalance_orig,

        oldbalance_dest=oldbalance_dest,
        newbalance_dest=newbalance_dest,
        step=customer.step,
        transaction_type=random.choice(TRANSACTION_TYPES),
    )

    
    # Update account states
    

    customer.record_transaction(amount)
    destination.receive_transaction(amount)

    return transaction