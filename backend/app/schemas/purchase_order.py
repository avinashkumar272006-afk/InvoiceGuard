from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import date
from decimal import Decimal
from app.models.purchase_order import POStatus

class PurchaseOrderItemBase(BaseModel):
    description: str = Field(..., max_length=500)
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    total_price: Decimal = Field(..., ge=0)

class PurchaseOrderItemCreate(PurchaseOrderItemBase):
    pass

class PurchaseOrderItemRead(PurchaseOrderItemBase):
    id: int
    po_id: int

    model_config = ConfigDict(from_attributes=True)

class PurchaseOrderBase(BaseModel):
    po_number: str = Field(..., max_length=100)
    vendor_id: int
    issue_date: date
    total_amount: Decimal = Field(..., ge=0)
    status: POStatus = POStatus.PENDING

class PurchaseOrderCreate(PurchaseOrderBase):
    items: List[PurchaseOrderItemCreate]

class PurchaseOrderUpdate(BaseModel):
    status: Optional[POStatus] = None

class PurchaseOrderRead(PurchaseOrderBase):
    id: int
    items: List[PurchaseOrderItemRead] = []

    model_config = ConfigDict(from_attributes=True)
