import pytest
from pydantic import ValidationError
from decimal import Decimal
from app.schemas.vendor import VendorCreate
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderItemCreate
from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate

def test_valid_vendor_create():
    vendor = VendorCreate(name="Test Vendor", tax_id="TAX123", contact_email="test@example.com")
    assert vendor.name == "Test Vendor"
    assert vendor.tax_id == "TAX123"
    assert vendor.contact_email == "test@example.com"

def test_invalid_email_vendor_create():
    with pytest.raises(ValidationError):
        VendorCreate(name="Test Vendor", contact_email="invalid-email")

def test_valid_po_create():
    po = PurchaseOrderCreate(
        po_number="PO-001",
        vendor_id=1,
        issue_date="2023-10-01",
        total_amount=Decimal("100.50"),
        items=[
            PurchaseOrderItemCreate(
                description="Item 1",
                quantity=Decimal("10.0"),
                unit_price=Decimal("10.05"),
                total_price=Decimal("100.50")
            )
        ]
    )
    assert po.po_number == "PO-001"
    assert len(po.items) == 1

def test_invalid_negative_amount_po_create():
    with pytest.raises(ValidationError):
        PurchaseOrderCreate(
            po_number="PO-001",
            vendor_id=1,
            issue_date="2023-10-01",
            total_amount=Decimal("-10.00"),  # Invalid
            items=[]
        )

def test_invalid_zero_quantity_po_item_create():
    with pytest.raises(ValidationError):
        PurchaseOrderItemCreate(
            description="Item",
            quantity=Decimal("0"),  # Must be strictly > 0
            unit_price=Decimal("10.00"),
            total_price=Decimal("0.00")
        )

def test_invalid_negative_quantity_invoice_item_create():
    with pytest.raises(ValidationError):
        InvoiceItemCreate(
            description="Item",
            quantity=Decimal("-5"),
            unit_price=Decimal("10.00"),
            total_price=Decimal("-50.00")
        )
