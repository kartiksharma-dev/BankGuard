from pathlib import Path
import threading

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

_preprocessor = None
_preprocessor_lock = threading.Lock()


def load_preprocessor():
    """Load the existing Phase 2 engineered preprocessor once in a thread-safe manner and reuse it."""
    global _preprocessor

    if _preprocessor is None:
        with _preprocessor_lock:
            if _preprocessor is None:
                if not PREPROCESSOR_PATH.exists():
                    raise FileNotFoundError(
                        f"Preprocessor not found: {PREPROCESSOR_PATH}"
                    )
                _preprocessor = joblib.load(PREPROCESSOR_PATH)

    return _preprocessor


def reset_preprocessor_cache() -> None:
    """Reset the in-memory cached preprocessor (used for testing and cache invalidation)."""
    global _preprocessor
    with _preprocessor_lock:
        _preprocessor = None


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
