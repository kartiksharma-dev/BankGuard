from pathlib import Path

import joblib
import pandas as pd

from simulator.feature_mapping import map_transaction_to_features
from simulator.schemas import Transaction


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PREPROCESSOR_PATH = (
    PROJECT_ROOT
    / "ml"
    / "artifacts"
    / "preprocessors"
    / "engineered_preprocessor.pkl"
)


EXPECTED_FEATURES = [
    "step",
    "type",
    "amount",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
    "isFlaggedFraud",
    "balance_change_orig",
    "balance_change_dest",
    "balance_error_orig",
    "balance_error_dest",
    "amount_to_old_balance_ratio",
    "amount_to_new_balance_ratio",
    "amount_to_old_dest_balance_ratio",
    "transaction_hour",
    "transaction_day",
]


def load_preprocessor():
    """Load the existing Phase 2 engineered preprocessor."""

    if not PREPROCESSOR_PATH.exists():
        raise FileNotFoundError(
            f"Preprocessor not found: {PREPROCESSOR_PATH}"
        )

    return joblib.load(PREPROCESSOR_PATH)


def transform_transaction(transaction: Transaction):
    """
    Convert a simulator transaction into the 21-feature
    representation expected by the production model.
    """

    features = map_transaction_to_features(transaction)

    df = pd.DataFrame(
        [features],
        columns=EXPECTED_FEATURES,
    )

    preprocessor = load_preprocessor()

    transformed = preprocessor.transform(df)

    return transformed