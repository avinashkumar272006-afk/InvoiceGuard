import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Tuple, Optional
from sqlalchemy.orm import Session

from app.schemas.extraction import ExtractedInvoiceSchema
from app.models.vendor import Vendor
from app.models.invoice import Invoice
from app.schemas.business_validation import BusinessValidationResult, BusinessValidationIssue

def _normalize_string(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r'\s+', ' ', s.strip())
    return s.lower()

def _parse_decimal(value_str: Optional[str]) -> Optional[Decimal]:
    if not value_str:
        return None
    try:
        return Decimal(value_str)
    except InvalidOperation:
        return None

def parse_unambiguous_date(date_str: str) -> Tuple[Optional[date], bool]:
    date_str = date_str.strip()
    # YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        try:
            return date.fromisoformat(date_str), False
        except ValueError:
            return None, False
            
    # Ambiguous formats MM/DD/YYYY vs DD/MM/YYYY
    if re.match(r"^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}$", date_str):
        parts = re.split(r"[/\-]", date_str)
        p1, p2, p3 = int(parts[0]), int(parts[1]), int(parts[2])
        if p1 <= 12 and p2 <= 12:
            return None, True # strictly ambiguous
            
    # Try some standard unambiguous formats if not ISO
    for fmt in ["%d %b %Y", "%b %d, %Y", "%d %B %Y", "%B %d, %Y"]:
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, fmt)
            return dt.date(), False
        except ValueError:
            pass
            
    return None, False

class BusinessValidationService:
    @staticmethod
    def validate(db: Session, extracted: ExtractedInvoiceSchema) -> BusinessValidationResult:
        issues = []
        warnings = list(extracted.metadata.warnings)
        
        # 1. Date
        parsed_date = None
        if extracted.metadata.ambiguous_date:
            issues.append(BusinessValidationIssue(code="DATE_AMBIGUOUS", message="Date flagged as ambiguous by extractor", field="issue_date_raw"))
        elif not extracted.issue_date_raw:
            issues.append(BusinessValidationIssue(code="MISSING_CRITICAL_FIELD", message="Issue date is missing", field="issue_date_raw"))
        else:
            dt, is_ambiguous = parse_unambiguous_date(extracted.issue_date_raw)
            if is_ambiguous:
                issues.append(BusinessValidationIssue(code="DATE_AMBIGUOUS", message=f"Date format {extracted.issue_date_raw} is ambiguous", field="issue_date_raw"))
            elif not dt:
                issues.append(BusinessValidationIssue(code="DATE_MALFORMED", message=f"Could not parse date {extracted.issue_date_raw}", field="issue_date_raw"))
            else:
                parsed_date = dt

        # 2. Numerics
        subtotal = _parse_decimal(extracted.subtotal)
        tax_amount = _parse_decimal(extracted.tax_amount)
        total_amount = _parse_decimal(extracted.total_amount)
        
        if extracted.subtotal and subtotal is None:
            issues.append(BusinessValidationIssue(code="NUMERIC_MALFORMED", message="Subtotal is malformed", field="subtotal"))
        if extracted.tax_amount and tax_amount is None:
            issues.append(BusinessValidationIssue(code="NUMERIC_MALFORMED", message="Tax amount is malformed", field="tax_amount"))
        if extracted.total_amount and total_amount is None:
            issues.append(BusinessValidationIssue(code="NUMERIC_MALFORMED", message="Total amount is malformed", field="total_amount"))
        elif not extracted.total_amount:
            issues.append(BusinessValidationIssue(code="MISSING_CRITICAL_FIELD", message="Total amount is missing", field="total_amount"))
            
        if subtotal is not None and subtotal < Decimal("0"):
            issues.append(BusinessValidationIssue(code="NEGATIVE_MONETARY", message="Subtotal cannot be negative", field="subtotal"))
        if tax_amount is not None and tax_amount < Decimal("0"):
            issues.append(BusinessValidationIssue(code="NEGATIVE_MONETARY", message="Tax amount cannot be negative", field="tax_amount"))
        if total_amount is not None and total_amount < Decimal("0"):
            issues.append(BusinessValidationIssue(code="NEGATIVE_MONETARY", message="Total amount cannot be negative", field="total_amount"))

        # Invoice Arithmetic
        if subtotal is not None and tax_amount is not None and total_amount is not None:
            if subtotal + tax_amount != total_amount:
                issues.append(BusinessValidationIssue(code="ARITHMETIC_MISMATCH", message="Subtotal + tax != total", field="total_amount"))
                
        # Line items
        for idx, item in enumerate(extracted.items):
            q = _parse_decimal(item.quantity)
            up = _parse_decimal(item.unit_price)
            tp = _parse_decimal(item.total_price)
            
            if q is None or up is None or tp is None:
                issues.append(BusinessValidationIssue(code="NUMERIC_MALFORMED", message="Line item numeric fields malformed", line_item_index=idx))
                continue
                
            if q <= Decimal("0"):
                issues.append(BusinessValidationIssue(code="NEGATIVE_QUANTITY", message="Quantity must be > 0", line_item_index=idx))
            if up < Decimal("0") or tp < Decimal("0"):
                issues.append(BusinessValidationIssue(code="NEGATIVE_MONETARY", message="Line item prices cannot be negative", line_item_index=idx))
                
            if q is not None and up is not None and tp is not None:
                if q * up != tp:
                    issues.append(BusinessValidationIssue(code="LINE_ARITHMETIC_MISMATCH", message="Quantity * Unit Price != Total Price", line_item_index=idx))

        # Vendor Resolution
        resolved_vendor_id = None
        if not extracted.vendor_tax_id and not extracted.vendor_name_raw:
            issues.append(BusinessValidationIssue(code="MISSING_CRITICAL_FIELD", message="Vendor details missing", field="vendor"))
        else:
            resolved_by_tax = None
            if extracted.vendor_tax_id:
                resolved_by_tax = db.query(Vendor).filter(Vendor.tax_id == extracted.vendor_tax_id).first()
                
            resolved_by_name = []
            if extracted.vendor_name_raw:
                normalized_name = _normalize_string(extracted.vendor_name_raw)
                all_vendors = db.query(Vendor).all()
                for v in all_vendors:
                    if _normalize_string(v.name) == normalized_name:
                        resolved_by_name.append(v)
                        
            if resolved_by_tax:
                resolved_vendor_id = resolved_by_tax.id
                if extracted.vendor_name_raw:
                    tax_v_norm = _normalize_string(resolved_by_tax.name)
                    req_v_norm = _normalize_string(extracted.vendor_name_raw)
                    if tax_v_norm != req_v_norm:
                        # Tax ID matches, but name doesn't match. Leave unresolved instead of failing.
                        resolved_vendor_id = None
            elif extracted.vendor_tax_id and not resolved_by_tax:
                if resolved_by_name:
                    if len(resolved_by_name) == 1:
                        resolved_vendor_id = resolved_by_name[0].id
                    # If ambiguous or not found, we simply leave resolved_vendor_id as None.
            else:
                if len(resolved_by_name) == 1:
                    resolved_vendor_id = resolved_by_name[0].id
                # If ambiguous or not found, we simply leave resolved_vendor_id as None.

        # Invoice duplicate check
        if not extracted.invoice_number:
            issues.append(BusinessValidationIssue(code="MISSING_CRITICAL_FIELD", message="Invoice number is missing", field="invoice_number"))
        else:
            if resolved_vendor_id:
                duplicate = db.query(Invoice).filter(Invoice.vendor_id == resolved_vendor_id, Invoice.invoice_number == extracted.invoice_number).first()
                if duplicate:
                    issues.append(BusinessValidationIssue(code="DUPLICATE_INVOICE", message="Invoice already exists for this vendor", field="invoice_number"))

        return BusinessValidationResult(
            is_valid=len(issues) == 0,
            vendor_id=resolved_vendor_id,
            vendor_name_raw=extracted.vendor_name_raw,
            parsed_issue_date=parsed_date,
            parsed_subtotal=subtotal,
            parsed_tax_amount=tax_amount,
            parsed_total_amount=total_amount,
            issues=issues,
            warnings=warnings
        )
