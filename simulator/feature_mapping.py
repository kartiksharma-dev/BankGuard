import math
from simulator.schemas import Transaction

def map_transaction_to_features(transaction: Transaction) -> dict:
    """
    Convert a BankGuard transaction into the feature representation
    used by the Phase 2 fraud model.
    """

    # PaySim-compatible raw features

    oldbalanceOrg =transaction.oldbalance_org
    newbalanceOrig = transaction.newbalance_orig

    oldbalanceDest = transaction.oldbalance_dest
    newbalanceDest = transaction.newbalance_dest

    amount = transaction.amount
    step = transaction.step

    # The current simulator does not have a separate
    # isFlaggedFraud business rule.

    isFlaggedFraud = 0

     # Engineered features

    balance_change_orig = (
        oldbalanceOrg - newbalanceOrig
     )

    balance_change_dest = (
        newbalanceDest - oldbalanceDest
    )

    balance_error_orig =(
        oldbalanceOrg - amount - newbalanceOrig
    )

    balance_error_dest =(
        oldbalanceDest + amount - newbalanceDest
    )

    amount_to_old_balance_ratio = (
        amount / (oldbalanceOrg +1)
    )

    amount_to_new_balance_ratio = (
        amount / (newbalanceOrig + 1)
    )

    amount_to_old_dest_balance_ratio = (
        amount / (oldbalanceDest + 1)
    )

    transaction_hour = step % 24
    transaction_day = step // 24

    features = {
        # Original PaySim-compatible features
        "step": step,
        "type": transaction.transaction_type,
        "amount": amount,
        "oldbalanceOrg": oldbalanceOrg,
        "newbalanceOrig": newbalanceOrig,
        "oldbalanceDest": oldbalanceDest,
        "newbalanceDest": newbalanceDest,
        "isFlaggedFraud": isFlaggedFraud,

        # Engineered features
        "balance_change_orig": balance_change_orig,
        "balance_change_dest": balance_change_dest,
        "balance_error_orig": balance_error_orig,
        "balance_error_dest": balance_error_dest,
        "amount_to_old_balance_ratio": amount_to_old_balance_ratio,
        "amount_to_new_balance_ratio": amount_to_new_balance_ratio,
        "amount_to_old_dest_balance_ratio": amount_to_old_dest_balance_ratio,
        "transaction_hour": transaction_hour,
        "transaction_day": transaction_day,
    }


     # Safety check

    for key, value in features.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(
                f"Invalid feature value for '{key}': {value}"
            )

    return features