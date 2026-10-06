import mlflow
import numpy as np


MLFLOW_TRACKING_URI = "http://127.0.0.1:5000"
MODEL_URI = "models:/BankGuard-Fraud-XGBoost@production"


def load_production_model():
    """Load the production fraud detection model from MLflow."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    return mlflow.pyfunc.load_model(MODEL_URI)


def predict_fraud(processed_features):
    """Predict whether a transaction is fraudulent."""

    model = load_production_model()

    prediction = model.predict(processed_features)
    prediction = np.asarray(prediction)

    fraud_prediction = int(prediction[0])

    return {
        "fraud_prediction": fraud_prediction
    }