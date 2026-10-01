from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

class ReviewCreate(BaseModel):
    status: str = Field(..., description="Target status (e.g., VERIFIED or DISPUTED)")
    actor: str = Field(..., max_length=255)
    comment: Optional[str] = Field(None, max_length=1000)

class ExceptionResolveCreate(BaseModel):
    actor: str = Field(..., max_length=255)
    comment: Optional[str] = Field(None, max_length=1000)

class AuditLogRead(BaseModel):
    id: int
    invoice_id: int
    actor: str
    action: str
    entity_name: str
    entity_id: Optional[int] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
