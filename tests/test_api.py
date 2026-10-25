from datetime import datetime

from fastapi.testclient import TestClient

from backend.app.main import app
from simulator.schemas import Transaction
from simulator.scenarios import TransactionScenario


client = TestClient(app)


def make_transaction():
    return Transaction(
        transaction_id="TXTEST001",
        customer_id="CTEST001",
        amount=1500.0,
        merchant_category="GROCERY",
        device_id="D101",
        location="Mumbai",
        timestamp=datetime(2026, 10, 24, 22, 30, 0),
        payment_method="UPI",
        transaction_type="PAYMENT",
        oldbalance_org=10000.0,
        newbalance_orig=8500.0,
        oldbalance_dest=5000.0,
        newbalance_dest=6500.0,
        step=1,
    )


def test_risk_endpoint_response_contract(monkeypatch):
    def fake_score(transaction):
        return {
            "transaction_id": transaction.transaction_id,
            "customer_id": transaction.customer_id,
            "amount": transaction.amount,
            "fraud_prediction": 0,
        }

    monkeypatch.setattr(
        "backend.app.api.risk.score_submitted_transaction",
        fake_score,
    )

    response = client.post(
        "/api/v1/risk/score",
        json=make_transaction().model_dump(mode="json"),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["transaction_id"] == "TXTEST001"
    assert data["customer_id"] == "CTEST001"
    assert data["amount"] == 1500.0
    assert data["fraud_prediction"] == 0


def test_risk_endpoint_rejects_invalid_amount():
    payload = make_transaction().model_dump(mode="json")
    payload["amount"] = -100

    response = client.post(
        "/api/v1/risk/score",
        json=payload,
    )

    assert response.status_code == 422


def test_simulator_endpoint_response_contract(monkeypatch):
    transaction = make_transaction()

    def fake_score_transaction(scenario):
        return {
            "transaction": transaction,
            "fraud_prediction": 0,
            "behavioral_features": {
                "new_device": 0,
                "unusual_location": 0,
                "high_velocity": 1,
            },
        }

    monkeypatch.setattr(
        "backend.app.api.simulator.score_transaction",
        fake_score_transaction,
    )

    response = client.post(
        "/api/v1/simulator/transactions",
        json={"scenario": "HIGH_VELOCITY"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["transaction"]["transaction_id"] == "TXTEST001"
    assert data["fraud_prediction"] == 0
    assert data["behavioral_features"]["high_velocity"] == 1
    assert data["risk_assessment"]["model_prediction"] == 0
    assert data["risk_assessment"]["behavioral_risk_score"] == 40
    assert data["risk_assessment"]["risk_level"] == "MEDIUM"
    assert data["risk_assessment"]["recommended_action"] == "REVIEW"


def test_simulator_rejects_invalid_scenario():
    response = client.post(
        "/api/v1/simulator/transactions",
        json={"scenario": "INVALID_SCENARIO"},
    )

    assert response.status_code == 422
