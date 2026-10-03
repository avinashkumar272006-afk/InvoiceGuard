from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.invoice_document import DocumentStatus

class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    status: DocumentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DocumentProcessingResponse(BaseModel):
    success: bool
    message: str
    invoice_id: Optional[int] = None

class DocumentUrlResponse(BaseModel):
    url: str
    expires_in: int
