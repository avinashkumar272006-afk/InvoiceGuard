import pytest
from pydantic import ValidationError
from app.schemas.extraction import (
    ExtractedInvoiceSchema,
    ExtractedInvoiceItem,
    ExtractionMetadata,
)

def test_valid_complete_extraction_payload():
    payload = {
        "invoice_number": "INV-1001",
        "issue_date_raw": "01/02/2026",
        "vendor_name_raw": "ACME Corp",
        "vendor_tax_id": "GSTIN123",
        "po_number": "PO-1001",
        "subtotal": "10000.00",
        "tax_amount": "1800.00",
        "total_amount": "11800.00",
        "currency": "INR",
        "items": [
            {
                "description": "Laptop",
                "quantity": "2",
                "unit_price": "5000.00",
                "total_price": "10000.00"
            }
        ],
        "metadata": {
            "warnings": ["Blurry vendor name"],
            "ambiguous_date": False
        }
    }
    schema = ExtractedInvoiceSchema(**payload)
    assert schema.invoice_number == "INV-1001"
    assert schema.issue_date_raw == "01/02/2026"
    assert schema.subtotal == "10000.00"
    assert schema.items[0].description == "Laptop"
    assert schema.items[0].quantity == "2"
    assert schema.metadata.warnings == ["Blurry vendor name"]

def test_valid_payload_with_optional_fields_missing():
    payload = {
        "issue_date_raw": "Feb 1, 2026",
        "metadata": {
            "warnings": [],
            "ambiguous_date": True
        }
    }
    schema = ExtractedInvoiceSchema(**payload)
    assert schema.invoice_number is None
    assert schema.vendor_name_raw is None
    assert schema.po_number is None
    assert schema.subtotal is None
    assert schema.currency is None
    assert schema.items == []
    assert schema.metadata.ambiguous_date is True

def test_decimal_like_strings_accepted():
    item = ExtractedInvoiceItem(
        description="Test",
        quantity="1.5",
        unit_price="49.99",
        total_price="74.985"
    )
    assert item.quantity == "1.5"
    assert item.unit_price == "49.99"

def test_float_like_numeric_input_rejected():
    payload = {
        "issue_date_raw": "2026-02-01",
        "subtotal": 10000.0,
        "metadata": {"warnings": [], "ambiguous_date": False}
    }
    with pytest.raises(ValidationError) as exc_info:
        ExtractedInvoiceSchema(**payload)
    assert "must be a string" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        ExtractedInvoiceItem(
            description="Test",
            quantity=2,
            unit_price=5000.0,
            total_price=10000.0
        )
    assert "must be a string" in str(exc_info.value)

def test_empty_numeric_strings_rejected():
    with pytest.raises(ValidationError) as exc_info:
        ExtractedInvoiceItem(
            description="Test",
            quantity="",
            unit_price="  ",
            total_price="10.0"
        )
    assert "cannot be empty" in str(exc_info.value)

def test_invalid_numeric_strings_rejected():
    with pytest.raises(ValidationError) as exc_info:
        ExtractedInvoiceItem(
            description="Test",
            quantity="two",
            unit_price="10.0",
            total_price="20.0"
        )
    assert "must be a valid numeric string" in str(exc_info.value)

def test_negative_quantity_rejected():
    with pytest.raises(ValidationError) as exc_info:
        ExtractedInvoiceItem(
            description="Test",
            quantity="-1",
            unit_price="10.0",
            total_price="10.0"
        )
    assert "quantity must be strictly greater than 0" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        ExtractedInvoiceItem(
            description="Test",
            quantity="0",
            unit_price="10.0",
            total_price="10.0"
        )
    assert "quantity must be strictly greater than 0" in str(exc_info.value)

def test_negative_prices_rejected():
    with pytest.raises(ValidationError) as exc_info:
        ExtractedInvoiceItem(
            description="Test",
            quantity="1",
            unit_price="-10.0",
            total_price="10.0"
        )
    assert "cannot be negative" in str(exc_info.value)

def test_empty_item_description_rejected():
    with pytest.raises(ValidationError) as exc_info:
        ExtractedInvoiceItem(
            description="",
            quantity="1",
            unit_price="10.0",
            total_price="10.0"
        )
    assert "String should have at least 1 character" in str(exc_info.value)

def test_empty_issue_date_raw_rejected():
    with pytest.raises(ValidationError) as exc_info:
        ExtractedInvoiceSchema(
            issue_date_raw="",
            metadata={"warnings": [], "ambiguous_date": False}
        )
    assert "String should have at least 1 character" in str(exc_info.value)

def test_arithmetic_mismatch_not_rejected_at_schema_level():
    # quantity * unit_price != total_price
    item = ExtractedInvoiceItem(
        description="Test",
        quantity="2",
        unit_price="10.00",
        total_price="999.00"
    )
    assert item.total_price == "999.00"

def test_extra_ai_fields_follow_default_behavior():
    # By default in Pydantic v2, extra fields are ignored unless config says otherwise
    payload = {
        "issue_date_raw": "01/02/2026",
        "metadata": {"warnings": [], "ambiguous_date": False},
        "extra_field_from_ai": "some value"
    }
    schema = ExtractedInvoiceSchema(**payload)
    assert not hasattr(schema, "extra_field_from_ai")
