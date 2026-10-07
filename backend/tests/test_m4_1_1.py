from app.database.connection import SessionLocal
from app.models.invoice import Invoice
from app.models.vendor import Vendor
from app.models.verification import ExceptionType
from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate
from datetime import date
from decimal import Decimal
import uuid

def test_vendor_unresolved_enum():
    # Verify the enum is present
    assert "VENDOR_UNRESOLVED" in ExceptionType.__members__
    assert ExceptionType.VENDOR_UNRESOLVED == "VENDOR_UNRESOLVED"

def test_invoice_model_nullable_vendor_and_raw_name():
    db = SessionLocal()
    try:
        # 1. Create a dummy vendor to test existing relationship works
        vendor = Vendor(name="Test Vendor 1")
        db.add(vendor)
        db.commit()

        # 2. Test an invoice WITH a vendor (existing behavior)
        inv1 = Invoice(
            invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
            vendor_id=vendor.id,
            issue_date=date(2023, 10, 1),
            total_amount=Decimal("100.00")
        )
        db.add(inv1)
        db.commit()
        assert inv1.id is not None
        assert inv1.vendor_id == vendor.id

        # 3. Test an invoice WITHOUT a vendor (new behavior)
        inv_number_2 = f"INV-{uuid.uuid4().hex[:8]}"
        inv2 = Invoice(
            invoice_number=inv_number_2,
            vendor_id=None,
            vendor_name_raw="Extracted Vendor Corp",
            issue_date=date(2023, 10, 2),
            total_amount=Decimal("200.00")
        )
        db.add(inv2)
        db.commit()
        
        # Reload to ensure it persisted properly
        db.refresh(inv2)
        assert inv2.id is not None
        assert inv2.vendor_id is None
        assert inv2.vendor_name_raw == "Extracted Vendor Corp"

    finally:
        # Cleanup
        db.query(Invoice).filter(Invoice.vendor_name_raw == "Extracted Vendor Corp").delete()
        if 'inv1' in locals():
            db.delete(inv1)
        if 'vendor' in locals():
            db.delete(vendor)
        db.commit()
        db.close()

def test_schema_supports_nullable_vendor():
    # InvoiceCreate schema should allow vendor_id=None and vendor_name_raw
    payload = {
        "invoice_number": "INV-12345",
        "vendor_id": None,
        "vendor_name_raw": "Unknown LLC",
        "issue_date": "2023-10-01",
        "total_amount": "500.00",
        "items": [
            {
                "description": "Services",
                "quantity": "1",
                "unit_price": "500.00",
                "total_price": "500.00"
            }
        ]
    }
    invoice_create = InvoiceCreate(**payload)
    assert invoice_create.vendor_id is None
    assert invoice_create.vendor_name_raw == "Unknown LLC"
