from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date
from decimal import Decimal

class BusinessValidationIssue(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
    severity: str = "ERROR"
    line_item_index: Optional[int] = None

class BusinessValidationResult(BaseModel):
    is_valid: bool
    vendor_id: Optional[int] = None
    parsed_issue_date: Optional[date] = None
    parsed_subtotal: Optional[Decimal] = None
    parsed_tax_amount: Optional[Decimal] = None
    parsed_total_amount: Optional[Decimal] = None
    issues: List[BusinessValidationIssue]
    warnings: List[str]
