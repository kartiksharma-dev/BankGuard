from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AlertCreate(BaseModel):
    """Request schema for creating an alert."""

    transaction_id: str = Field(min_length=1, max_length=100)
    alert_type: str = Field(min_length=1, max_length=100)


class AlertResponse(BaseModel):
    """Response schema for an alert."""

    model_config = ConfigDict(from_attributes=True)

    alert_id: int
    transaction_id: str
    alert_type: str
    status: str
    created_at: datetime