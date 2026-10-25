from datetime import timedelta
from simulator.customer import DestinationAccount
from simulator.generator import create_customer, generate_transaction
from simulator.preprocessing import transform_transaction
from simulator.model_scoring import predict_fraud
from simulator.behavioral_features import calculate_behavioral_features
from simulator.scenarios import TransactionScenario


def score_transaction(
    scenario: TransactionScenario = TransactionScenario.NORMAL,
) -> dict:
    """Generate and score a transaction for the requested scenario."""

    # 1. Create a customer and destination account.
    customer = create_customer()
    destination = DestinationAccount(
        account_id="DST_SIMULATION",
    )

    # 2. Generate the transaction.
    if scenario == TransactionScenario.HIGH_VELOCITY:
        previous_timestamp = None

        # Generate three transactions for the same customer.
        for _ in range(3):
            transaction = generate_transaction(
                scenario=TransactionScenario.HIGH_VELOCITY,
                customer=customer,
                destination=destination,
                previous_timestamp=previous_timestamp,
            )

            previous_timestamp = transaction.timestamp

    else:
        transaction = generate_transaction(
            scenario=scenario,
            customer=customer,
            destination=destination,
        )

    # 3. Apply the existing preprocessing pipeline.
    processed_features = transform_transaction(transaction)

    # 4. Score the final transaction using the existing model.
    model_result = predict_fraud(processed_features)

    # 5. Calculate behavioral risk features.
    behavioral_features = calculate_behavioral_features(
        transaction,
        customer,
    )

    # 6. Preserve the existing response structure.
    return {
        "transaction": transaction,
        "fraud_prediction": model_result["fraud_prediction"],
        "behavioral_features": behavioral_features,
    }
