from typing import Any


# Initial prototype weights, not calibrated fraud probabilities.
BEHAVIORAL_WEIGHTS = {
    "new_device": 20,
    "unusual_location": 20,
    "high_velocity": 40,
}

MAX_RISK_SCORE = 100


def calculate_behavioral_risk(
    behavioral_features: dict[str, Any],
) -> int:
    """
    Calculate a prototype behavioral risk score.

    Each recognized indicator must be 0 or 1.
    The result is capped at 100.
    """
    score = 0

    for feature, weight in BEHAVIORAL_WEIGHTS.items():
        value = behavioral_features.get(feature, 0)

        if value not in (0, 1):
            raise ValueError(
                f"Behavioral feature '{feature}' must be 0 or 1."
            )

        score += weight * value

    return min(score, MAX_RISK_SCORE)


def assess_transaction_risk(
    fraud_prediction: int,
    behavioral_features: dict[str, Any],
) -> dict[str, Any]:
    """
    Combine the existing model prediction with behavioral signals.

    The model prediction remains separate from the behavioral score.
    Risk levels and actions are preliminary prototype policies.
    """
    if fraud_prediction not in (0, 1):
        raise ValueError("fraud_prediction must be 0 or 1.")

    behavioral_score = calculate_behavioral_risk(
        behavioral_features
    )

    # Preliminary thresholds for the prototype only.
    if fraud_prediction == 1:
        risk_level = "HIGH"
        recommended_action = "REVIEW"
    elif behavioral_score >= 60:
        risk_level = "HIGH"
        recommended_action = "REVIEW"
    elif behavioral_score >= 20:
        risk_level = "MEDIUM"
        recommended_action = "REVIEW"
    else:
        risk_level = "LOW"
        recommended_action = "ALLOW"

    return {
        "model_prediction": fraud_prediction,
        "behavioral_risk_score": behavioral_score,
        "risk_level": risk_level,
        "recommended_action": recommended_action,
    }

