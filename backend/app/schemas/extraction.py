from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from decimal import Decimal, InvalidOperation

class ExtractedInvoiceItem(BaseModel):
    description: str = Field(..., min_length=1)
    quantity: str = Field(...)
    unit_price: str = Field(...)
    total_price: str = Field(...)

    @field_validator('quantity', 'unit_price', 'total_price', mode='before')
    @classmethod
    def ensure_string(cls, v, info):
        if not isinstance(v, str):
            raise ValueError(f"{info.field_name} must be a string")
        return v

    @field_validator('quantity', 'unit_price', 'total_price')
    @classmethod
    def validate_numeric_string(cls, v: str, info):
        v = v.strip()
        if not v:
            raise ValueError(f"{info.field_name} cannot be empty")
        
        try:
            val = Decimal(v)
        except InvalidOperation:
            raise ValueError(f"{info.field_name} must be a valid numeric string")
        
        if info.field_name == 'quantity':
            if val <= 0:
                raise ValueError("quantity must be strictly greater than 0")
        else:
            if val < 0:
                raise ValueError(f"{info.field_name} cannot be negative")
            
        return v


class ExtractionMetadata(BaseModel):
    warnings: List[str] = Field(default_factory=list)
    ambiguous_date: bool = False


class ExtractedInvoiceSchema(BaseModel):
    invoice_number: Optional[str] = Field(default=None)
    issue_date_raw: str = Field(..., min_length=1)
    vendor_name_raw: Optional[str] = Field(default=None)
    vendor_tax_id: Optional[str] = Field(default=None)
    po_number: Optional[str] = Field(default=None)
    
    subtotal: Optional[str] = Field(default=None)
    tax_amount: Optional[str] = Field(default=None)
    total_amount: Optional[str] = Field(default=None)
    currency: Optional[str] = Field(default=None)

    items: List[ExtractedInvoiceItem] = Field(default_factory=list)
    metadata: ExtractionMetadata

    @field_validator('subtotal', 'tax_amount', 'total_amount', mode='before')
    @classmethod
    def ensure_string_optional(cls, v, info):
        if v is not None and not isinstance(v, str):
            raise ValueError(f"{info.field_name} must be a string")
        return v

    @field_validator('invoice_number', 'currency', mode='before')
    @classmethod
    def trim_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator('subtotal', 'tax_amount', 'total_amount')
    @classmethod
    def validate_monetary_string(cls, v: str, info):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError(f"{info.field_name} cannot be empty")
        
        try:
            val = Decimal(v)
        except InvalidOperation:
            raise ValueError(f"{info.field_name} must be a valid numeric string")
        
        if val < 0:
            raise ValueError(f"{info.field_name} cannot be negative")
            
        return v
