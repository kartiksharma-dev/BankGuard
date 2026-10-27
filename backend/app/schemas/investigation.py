from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InvestigationCreate(BaseModel):
    alert_id: int = Field(gt=0)
    assigned_to: str | None = Field(default=None, max_length=100)


class InvestigationUpdate(BaseModel):
    assigned_to: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, min_length=1, max_length=30)
    findings: str | None = None


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    investigation_id: int
    alert_id: int
    assigned_to: str | None
    status: str
    findings: str | None
    created_at: datetime
    updated_at: datetime