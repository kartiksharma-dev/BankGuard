import pytest

from backend.app.services.risk_decision_engine import (
    assess_transaction_risk,
    calculate_behavioral_risk,
)


def test_no_behavioral_risk():
    result = assess_transaction_risk(
        fraud_prediction=0,
        behavioral_features={
            "new_device": 0,
            "unusual_location": 0,
            "high_velocity": 0,
        },
    )

    assert result["model_prediction"] == 0
    assert result["behavioral_risk_score"] == 0
    assert result["risk_level"] == "LOW"
    assert result["recommended_action"] == "ALLOW"


def test_new_device_requires_review():
    result = assess_transaction_risk(
        fraud_prediction=0,
        behavioral_features={
            "new_device": 1,
            "unusual_location": 0,
            "high_velocity": 0,
        },
    )

    assert result["behavioral_risk_score"] == 20
    assert result["risk_level"] == "MEDIUM"
    assert result["recommended_action"] == "REVIEW"


def test_high_velocity_requires_review():
    result = assess_transaction_risk(
        fraud_prediction=0,
        behavioral_features={
            "new_device": 0,
            "unusual_location": 0,
            "high_velocity": 1,
        },
    )

    assert result["behavioral_risk_score"] == 40
    assert result["risk_level"] == "MEDIUM"
    assert result["recommended_action"] == "REVIEW"


def test_multiple_behavioral_indicators_raise_risk():
    result = assess_transaction_risk(
        fraud_prediction=0,
        behavioral_features={
            "new_device": 1,
            "unusual_location": 0,
            "high_velocity": 1,
        },
    )

    assert result["behavioral_risk_score"] == 60
    assert result["risk_level"] == "HIGH"
    assert result["recommended_action"] == "REVIEW"


def test_model_fraud_prediction_requires_review():
    result = assess_transaction_risk(
        fraud_prediction=1,
        behavioral_features={
            "new_device": 0,
            "unusual_location": 0,
            "high_velocity": 0,
        },
    )

    assert result["model_prediction"] == 1
    assert result["behavioral_risk_score"] == 0
    assert result["risk_level"] == "HIGH"
    assert result["recommended_action"] == "REVIEW"


def test_invalid_behavioral_indicator_is_rejected():
    with pytest.raises(ValueError):
        calculate_behavioral_risk(
            {
                "new_device": 2,
                "unusual_location": 0,
                "high_velocity": 0,
            }
        )


def test_invalid_model_prediction_is_rejected():
    with pytest.raises(ValueError):
        assess_transaction_risk(
            fraud_prediction=2,
            behavioral_features={
                "new_device": 0,
                "unusual_location": 0,
                "high_velocity": 0,
            },
        )