from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional
from datetime import datetime

class VendorBase(BaseModel):
    name: str = Field(..., max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    contact_email: Optional[EmailStr] = None

class VendorCreate(VendorBase):
    pass

class VendorUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    contact_email: Optional[EmailStr] = None

class VendorRead(VendorBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
