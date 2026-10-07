import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from app.schemas.extraction import ExtractedInvoiceSchema, ExtractedInvoiceItem, ExtractionMetadata
from app.services.business_validation import BusinessValidationService
from app.models.vendor import Vendor
from app.models.invoice import Invoice
from app.schemas.business_validation import BusinessValidationResult

@pytest.fixture
def db_session():
    session = MagicMock()
    
    # Setup default query mock behavior (no vendor found, no duplicate invoice)
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None
    mock_query.all.return_value = []
    
    session.query.return_value = mock_query
    return session

def base_schema():
    return ExtractedInvoiceSchema(
        invoice_number="INV-001",
        issue_date_raw="2026-01-01",
        vendor_name_raw="Test Vendor",
        vendor_tax_id="TAX123",
        subtotal="100.00",
        tax_amount="10.00",
        total_amount="110.00",
        items=[
            ExtractedInvoiceItem(description="Item 1", quantity="2", unit_price="50.00", total_price="100.00")
        ],
        metadata=ExtractionMetadata()
    )

def test_valid_decimal_conversion_and_arithmetic(db_session):
    schema = base_schema()
    vendor = Vendor(id=1, name="Test Vendor", tax_id="TAX123")
    
    mock_query = MagicMock()
    db_session.query.return_value = mock_query
    mock_query.filter.return_value.first.side_effect = [vendor, None]
    
    result = BusinessValidationService.validate(db_session, schema)
    
    assert result.is_valid is True
    assert len(result.issues) == 0
    assert result.parsed_total_amount == Decimal("110.00")
    assert result.parsed_subtotal == Decimal("100.00")
    assert result.parsed_tax_amount == Decimal("10.00")

def test_malformed_numeric(db_session):
    schema = base_schema()
    schema.total_amount = "abc"
    result = BusinessValidationService.validate(db_session, schema)
    assert not result.is_valid
    assert any(i.code == "NUMERIC_MALFORMED" and i.field == "total_amount" for i in result.issues)

def test_negative_monetary(db_session):
    schema = base_schema()
    schema.tax_amount = "-10.00"
    result = BusinessValidationService.validate(db_session, schema)
    assert not result.is_valid
    assert any(i.code == "NEGATIVE_MONETARY" for i in result.issues)

def test_invalid_invoice_arithmetic(db_session):
    schema = base_schema()
    schema.total_amount = "200.00"
    result = BusinessValidationService.validate(db_session, schema)
    assert not result.is_valid
    assert any(i.code == "ARITHMETIC_MISMATCH" for i in result.issues)

def test_valid_line_arithmetic(db_session):
    schema = base_schema()
    result = BusinessValidationService.validate(db_session, schema)
    assert not any(i.code == "LINE_ARITHMETIC_MISMATCH" for i in result.issues)

def test_invalid_line_arithmetic(db_session):
    schema = base_schema()
    schema.items[0].total_price = "90.00"
    result = BusinessValidationService.validate(db_session, schema)
    assert not result.is_valid
    assert any(i.code == "LINE_ARITHMETIC_MISMATCH" for i in result.issues)

def test_valid_unambiguous_date(db_session):
    schema = base_schema()
    schema.issue_date_raw = "2026-09-29"
    result = BusinessValidationService.validate(db_session, schema)
    assert result.parsed_issue_date == date(2026, 9, 29)

def test_ambiguous_date(db_session):
    schema = base_schema()
    schema.issue_date_raw = "03/04/2026"
    result = BusinessValidationService.validate(db_session, schema)
    assert not result.is_valid
    assert any(i.code == "DATE_AMBIGUOUS" for i in result.issues)
    assert result.parsed_issue_date is None

def test_impossible_date(db_session):
    schema = base_schema()
    schema.issue_date_raw = "2026-02-30"
    result = BusinessValidationService.validate(db_session, schema)
    assert not result.is_valid
    assert any(i.code == "DATE_MALFORMED" for i in result.issues)

def test_malformed_date(db_session):
    schema = base_schema()
    schema.issue_date_raw = "Not a date"
    result = BusinessValidationService.validate(db_session, schema)
    assert not result.is_valid
    assert any(i.code == "DATE_MALFORMED" for i in result.issues)

def test_exact_tax_id_match(db_session):
    schema = base_schema()
    vendor = Vendor(id=5, name="Test Vendor", tax_id="TAX123")
    
    mock_query = MagicMock()
    db_session.query.return_value = mock_query
    mock_query.filter.return_value.first.side_effect = [vendor, None]
    
    result = BusinessValidationService.validate(db_session, schema)
    assert result.vendor_id == 5
    assert result.is_valid is True

def test_vendor_name_fallback(db_session):
    schema = base_schema()
    schema.vendor_tax_id = None
    vendor = Vendor(id=2, name="Test Vendor")
    
    mock_query = MagicMock()
    db_session.query.return_value = mock_query
    mock_query.all.return_value = [vendor]
    mock_query.filter.return_value.first.return_value = None
    
    result = BusinessValidationService.validate(db_session, schema)
    assert result.is_valid is True
    assert result.vendor_id == 2

def test_vendor_not_found(db_session):
    schema = base_schema()
    
    mock_query = MagicMock()
    db_session.query.return_value = mock_query
    mock_query.filter.return_value.first.return_value = None
    mock_query.all.return_value = []
    
    result = BusinessValidationService.validate(db_session, schema)
    # M4.1.2: Vendor not found no longer aborts processing
    assert result.is_valid is True
    assert result.vendor_id is None
    assert result.vendor_name_raw == "Test Vendor"

def test_duplicate_vendor_name_ambiguity(db_session):
    schema = base_schema()
    schema.vendor_tax_id = None
    
    v1 = Vendor(id=1, name="Test Vendor")
    v2 = Vendor(id=2, name="Test Vendor ")
    
    mock_query = MagicMock()
    db_session.query.return_value = mock_query
    mock_query.all.return_value = [v1, v2]
    
    result = BusinessValidationService.validate(db_session, schema)
    # M4.1.2: Ambiguous vendor no longer aborts processing
    assert result.is_valid is True
    assert result.vendor_id is None
    assert result.vendor_name_raw == "Test Vendor"

def test_tax_id_name_disagreement(db_session):
    schema = base_schema()
    vendor = Vendor(id=1, name="Different Vendor", tax_id="TAX123")
    
    mock_query = MagicMock()
    db_session.query.return_value = mock_query
    mock_query.filter.return_value.first.return_value = vendor
    
    result = BusinessValidationService.validate(db_session, schema)
    # M4.1.2: Mismatched vendor no longer aborts processing
    assert result.is_valid is True
    assert result.vendor_id is None
    assert result.vendor_name_raw == "Test Vendor"

def test_duplicate_invoice_same_vendor(db_session):
    schema = base_schema()
    vendor = Vendor(id=1, name="Test Vendor", tax_id="TAX123")
    invoice = Invoice(id=1, invoice_number="INV-001", vendor_id=1)
    
    mock_query = MagicMock()
    db_session.query.return_value = mock_query
    mock_query.filter.return_value.first.side_effect = [vendor, invoice]
    
    result = BusinessValidationService.validate(db_session, schema)
    assert not result.is_valid
    assert any(i.code == "DUPLICATE_INVOICE" for i in result.issues)

def test_same_invoice_number_different_vendor(db_session):
    schema = base_schema()
    vendor = Vendor(id=2, name="Test Vendor", tax_id="TAX123")
    
    mock_query = MagicMock()
    db_session.query.return_value = mock_query
    mock_query.filter.return_value.first.side_effect = [vendor, None]
    
    result = BusinessValidationService.validate(db_session, schema)
    assert result.is_valid is True

def test_missing_critical_fields(db_session):
    schema = base_schema()
    schema.invoice_number = None
    schema.total_amount = None
    
    result = BusinessValidationService.validate(db_session, schema)
    assert not result.is_valid
    assert any(i.code == "MISSING_CRITICAL_FIELD" and i.field == "invoice_number" for i in result.issues)
    assert any(i.code == "MISSING_CRITICAL_FIELD" and i.field == "total_amount" for i in result.issues)

def test_no_db_writes_occur(db_session):
    schema = base_schema()
    BusinessValidationService.validate(db_session, schema)
    db_session.add.assert_not_called()
    db_session.commit.assert_not_called()
    db_session.flush.assert_not_called()
