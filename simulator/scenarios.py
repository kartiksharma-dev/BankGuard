from enum import Enum


class TransactionScenario(str, Enum):
    NORMAL = "NORMAL"
    HIGH_AMOUNT = "HIGH_AMOUNT"
    NEW_DEVICE = "NEW_DEVICE"
    UNUSUAL_LOCATION = "UNUSUAL_LOCATION"
    HIGH_VELOCITY = "HIGH_VELOCITY"
