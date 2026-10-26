from sqlalchemy.exc import IntegrityError

from backend.app.db.session import SessionLocal
from backend.app.models.customer import Customer
from backend.app.models.transaction import Transaction as TransactionModel
from simulator.model_scoring import predict_fraud
from simulator.preprocessing import transform_transaction
from simulator.schemas import Transaction


def score_submitted_transaction(transaction: Transaction) -> dict:
    """
    Score a submitted transaction and persist it in PostgreSQL.

    Duplicate transaction IDs are rejected before model inference.
    Database changes are committed atomically.
    """
    with SessionLocal() as db:
        # Reject transactions that have already been recorded.
        existing_transaction = db.get(
            TransactionModel,
            transaction.transaction_id,
        )

        if existing_transaction is not None:
            raise ValueError(
                f"Transaction '{transaction.transaction_id}' already exists."
            )

        # Run the existing fraud-detection pipeline.
        processed_features = transform_transaction(transaction)
        model_result = predict_fraud(processed_features)
        fraud_prediction = int(model_result["fraud_prediction"])

        try:
            # Create the customer if they do not already exist.
            customer = db.get(Customer, transaction.customer_id)

            if customer is None:
                customer = Customer(
                    customer_id=transaction.customer_id,
                )
                db.add(customer)
                db.flush()

            # Save the scored transaction.
            saved_transaction = TransactionModel(
                transaction_id=transaction.transaction_id,
                customer_id=transaction.customer_id,
                amount=transaction.amount,
                merchant_category=transaction.merchant_category,
                device_id=transaction.device_id,
                location=transaction.location,
                timestamp=transaction.timestamp,
                payment_method=transaction.payment_method,
                transaction_type=transaction.transaction_type,
                oldbalance_org=transaction.oldbalance_org,
                newbalance_orig=transaction.newbalance_orig,
                oldbalance_dest=transaction.oldbalance_dest,
                newbalance_dest=transaction.newbalance_dest,
                step=transaction.step,
                fraud_prediction=fraud_prediction,
            )

            db.add(saved_transaction)
            db.commit()

        except IntegrityError as exc:
            db.rollback()
            raise ValueError(
                f"Transaction '{transaction.transaction_id}' "
                "could not be saved because of a database constraint."
            ) from exc

        except Exception:
            db.rollback()
            raise

    return {
        "transaction_id": transaction.transaction_id,
        "customer_id": transaction.customer_id,
        "amount": transaction.amount,
        "fraud_prediction": fraud_prediction,
    }