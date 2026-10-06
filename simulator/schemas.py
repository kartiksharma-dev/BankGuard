from datetime import datetime
from pydantic import BaseModel, Field


class Transaction(BaseModel):
    transaction_id: str
    customer_id: str

    amount: float = Field(gt=0)

    merchant_category: str
    device_id: str
    location: str

    timestamp: datetime
    payment_method: str
    transaction_type: str

    oldbalance_org: float = Field(ge=0)
    newbalance_orig: float = Field(ge=0)

    oldbalance_dest: float = Field(ge=0)
    newbalance_dest: float = Field(ge=0)

    step: int = Field(ge=0)