from pydantic import BaseModel, ConfigDict, Field, AliasPath
from typing import Optional, List
from datetime import date
from decimal import Decimal
import uuid
from app.models.invoice import InvoiceStatus

class InvoiceItemBase(BaseModel):
    description: str = Field(..., max_length=500)
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    total_price: Decimal = Field(..., ge=0)

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceItemRead(InvoiceItemBase):
    id: int
    invoice_id: int
    po_item_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class InvoiceBase(BaseModel):
    invoice_number: str = Field(..., max_length=100)
    vendor_id: Optional[int] = None
    vendor_name_raw: Optional[str] = Field(None, max_length=255)
    po_id: Optional[int] = None
    issue_date: date
    total_amount: Decimal = Field(..., ge=0)
    status: InvoiceStatus = InvoiceStatus.PENDING

class InvoiceCreate(InvoiceBase):
    items: List[InvoiceItemCreate]

class InvoiceUpdate(BaseModel):
    status: Optional[InvoiceStatus] = None

class InvoiceRead(InvoiceBase):
    id: int
    items: List[InvoiceItemRead] = []
    document_id: Optional[uuid.UUID] = Field(default=None, validation_alias=AliasPath("document", "id"))

    model_config = ConfigDict(from_attributes=True)

class InvoiceLinkPO(BaseModel):
    po_id: int
    actor: str = Field(..., max_length=255)
    comment: Optional[str] = Field(None, max_length=1000)

class InvoiceLinkVendor(BaseModel):
    vendor_id: int
    actor: str = Field(..., min_length=1, max_length=255)
    comment: Optional[str] = Field(None, max_length=1000)

class InvoiceItemMapPO(BaseModel):
    po_item_id: int
    actor: str = Field(..., min_length=1, max_length=255)
    comment: Optional[str] = Field(None, max_length=1000)

class InvoiceItemUnmapPO(BaseModel):
    actor: str = Field(..., min_length=1, max_length=255)
    comment: Optional[str] = Field(None, max_length=1000)
