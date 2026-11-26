from datetime import datetime, timezone
import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from backend.app.db.session import SessionLocal
from backend.app.models.alert import Alert
from backend.app.models.customer import Customer
from backend.app.models.transaction import Transaction as TransactionModel
from backend.app.services.risk_decision_engine import assess_transaction_risk
from backend.app.services.websocket_manager import ws_manager
from simulator.model_scoring import predict_fraud
from simulator.preprocessing import transform_transaction
from simulator.schemas import Transaction

logger = logging.getLogger(__name__)


def score_submitted_transaction(
    transaction: Transaction,
    behavioral_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Score a submitted transaction, perform multi-factor risk assessment,
    persist customer and transaction information to PostgreSQL, and
    automatically generate fraud alerts if the transaction meets ML fraud
    or high behavioral risk criteria.

    Duplicate transaction IDs are rejected before model inference.
    Duplicate alerts of the same type for the same transaction are prevented.
    Database changes across customer, transaction, and alerts are committed atomically.
    """
    if behavioral_features is None:
        behavioral_features = {
            "new_device": 0,
            "unusual_location": 0,
            "high_velocity": 0,
        }

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

        # Run the ML fraud-detection pipeline using the cached preprocessor.
        processed_features = transform_transaction(transaction)
        model_result = predict_fraud(processed_features)
        fraud_prediction = int(model_result["fraud_prediction"])

        # Run the Risk Decision Engine.
        risk_assessment = assess_transaction_risk(
            fraud_prediction=fraud_prediction,
            behavioral_features=behavioral_features,
        )

        created_alerts: list[dict[str, Any]] = []

        try:
            # 1. Upsert customer record if not already present.
            customer = db.get(Customer, transaction.customer_id)

            if customer is None:
                customer = Customer(
                    customer_id=transaction.customer_id,
                )
                db.add(customer)
                db.flush()

            # 2. Persist the scored transaction.
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
            db.flush()

            # 3. Automatic Fraud Alert Evaluation
            # Check existing alerts for this transaction to prevent duplicate alerts of the same type.
            existing_alerts_query = db.scalars(
                select(Alert.alert_type).where(
                    Alert.transaction_id == transaction.transaction_id
                )
            ).all()
            existing_alert_types = set(existing_alerts_query)

            # Evaluate alert conditions independently:
            # - ML_FRAUD_DETECTED: triggered when ML model predicts fraud (fraud_prediction == 1)
            # - HIGH_BEHAVIORAL_RISK: triggered when behavioral risk score meets existing high threshold (>= 60)
            eligible_alert_types: list[str] = []

            if fraud_prediction == 1:
                eligible_alert_types.append("ML_FRAUD_DETECTED")

            behavioral_score = risk_assessment.get("behavioral_risk_score", 0)
            if behavioral_score >= 60:
                eligible_alert_types.append("HIGH_BEHAVIORAL_RISK")

            for atype in eligible_alert_types:
                if atype not in existing_alert_types:
                    alert = Alert(
                        transaction_id=transaction.transaction_id,
                        alert_type=atype,
                        status="OPEN",
                    )
                    db.add(alert)
                    db.flush()
                    existing_alert_types.add(atype)
                    created_alerts.append({
                        "alert_id": alert.alert_id,
                        "transaction_id": alert.transaction_id,
                        "alert_type": alert.alert_type,
                        "status": alert.status,
                        "created_at": (
                            alert.created_at.isoformat()
                            if alert.created_at
                            else None
                        ),
                    })

            # 4. Atomic PostgreSQL Commit
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
        "risk_assessment": risk_assessment,
        "alert": created_alerts[0] if created_alerts else None,
        "alerts": created_alerts,
    }


async def broadcast_transaction_events(
    result: dict[str, Any],
    transaction: Transaction,
) -> None:
    """
    Safely broadcast ALERT_CREATED and TRANSACTION_PROCESSED telemetry events
    over WebSockets. Failures are non-fatal to preserve committed transactions.
    """
    try:
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Broadcast ALERT_CREATED event for each newly generated alert
        for alert_data in result.get("alerts", []):
            await ws_manager.broadcast({
                "type": "ALERT_CREATED",
                "timestamp": now_iso,
                "data": {
                    "alert": alert_data,
                },
            })

        # 2. Broadcast TRANSACTION_PROCESSED event
        tx_data = {
            "transaction_id": result["transaction_id"],
            "customer_id": result["customer_id"],
            "amount": result["amount"],
            "fraud_prediction": result["fraud_prediction"],
            "merchant_category": transaction.merchant_category,
            "device_id": transaction.device_id,
            "location": transaction.location,
            "timestamp": (
                transaction.timestamp.isoformat()
                if hasattr(transaction.timestamp, "isoformat")
                else str(transaction.timestamp)
            ),
            "payment_method": transaction.payment_method,
            "transaction_type": transaction.transaction_type,
            "oldbalance_org": transaction.oldbalance_org,
            "newbalance_orig": transaction.newbalance_orig,
            "oldbalance_dest": transaction.oldbalance_dest,
            "newbalance_dest": transaction.newbalance_dest,
            "step": transaction.step,
        }

        await ws_manager.broadcast({
            "type": "TRANSACTION_PROCESSED",
            "timestamp": now_iso,
            "data": {
                "transaction": tx_data,
                "risk_assessment": result["risk_assessment"],
                "alert": result.get("alert"),
            },
        })
    except Exception as ws_err:
        logger.warning(
            "Non-fatal error broadcasting WebSocket telemetry for transaction %s: %s",
            transaction.transaction_id,
            ws_err,
        )


async def process_and_broadcast_transaction(
    transaction: Transaction,
    behavioral_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Orchestrate transaction scoring, atomic database persistence, and WebSocket broadcasting.
    Executes synchronous ML inference and PostgreSQL operations in a worker thread,
    then broadcasts telemetry events on the async event loop after commit.
    """
    result = await run_in_threadpool(
        score_submitted_transaction,
        transaction,
        behavioral_features,
    )
    await broadcast_transaction_events(result, transaction)
    return result
