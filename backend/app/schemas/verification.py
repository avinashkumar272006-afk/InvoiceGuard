from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.models.verification import VerificationStatus, ExceptionType

class InvoiceExceptionRead(BaseModel):
    id: int
    verification_id: int
    exception_type: ExceptionType
    description: str
    resolved: bool

    model_config = ConfigDict(from_attributes=True)

class VerificationRead(BaseModel):
    id: int
    invoice_id: int
    status: VerificationStatus
    verified_at: Optional[datetime]
    exceptions: List[InvoiceExceptionRead] = []

    model_config = ConfigDict(from_attributes=True)

class ExceptionSummary(BaseModel):
    total: int
    resolved: int
    unresolved: int
    by_type: Optional[dict[str, int]] = None
