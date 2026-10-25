from simulator.model_scoring import predict_fraud
from simulator.preprocessing import transform_transaction
from simulator.schemas import Transaction


def score_submitted_transaction(transaction: Transaction) -> dict:
    """
    Score a caller-submitted transaction using the existing
    preprocessing pipeline and production fraud-detection model.
    """

    processed_features = transform_transaction(transaction)
    model_result = predict_fraud(processed_features)

    return {
        "transaction_id": transaction.transaction_id,
        "customer_id": transaction.customer_id,
        "amount": transaction.amount,
        "fraud_prediction": model_result["fraud_prediction"],
    }
