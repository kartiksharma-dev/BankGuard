from simulator.generator import create_customer, generate_transaction
from simulator.preprocessing import transform_transaction
from simulator.model_scoring import predict_fraud
from simulator.behavioral_features import calculate_behavioral_features
from simulator.scenarios import TransactionScenario


def score_transaction(
    scenario: TransactionScenario = TransactionScenario.NORMAL,
):
    # 1. Create customer
    customer = create_customer()

    # 2. Generate transaction
    transaction = generate_transaction(
        scenario=scenario,
        customer=customer,
    )

    # 3. Existing ML feature pipeline
    processed_features = transform_transaction(transaction)

    # 4. XGBoost production prediction
    model_result = predict_fraud(processed_features)

    # 5. Behavioral risk features
    behavioral_features = calculate_behavioral_features(
        transaction,
        customer,
    )

    return {
        "transaction": transaction,
        "fraud_prediction": model_result["fraud_prediction"],
        "behavioral_features": behavioral_features,
    }