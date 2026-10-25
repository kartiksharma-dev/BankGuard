import mlflow
import numpy as np
import logging

MLFLOW_TRACKING_URI = "http://127.0.0.1:5000"
MODEL_URI = "models:/BankGuard-Fraud-XGBoost@production"

logger = logging.getLogger(__name__)
_model = None

def load_production_model():
    """Load the production fraud detection model once and resue it."""
    global _model

    if _model is None:
        logger.info("Loading production fraud detection model from MLflow...")

        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        _model = mlflow.pyfunc.load_model(MODEL_URI)

        logger.info("Production fraud detection model loaded successfully. ")
    return _model
def predict_fraud(processed_features):
    """Predict whether a transaction is fraudulent."""

    model = load_production_model()

    prediction = model.predict(processed_features)
    prediction = np.asarray(prediction)

    fraud_prediction = int(prediction[0])

    return {
        "fraud_prediction": fraud_prediction
    }