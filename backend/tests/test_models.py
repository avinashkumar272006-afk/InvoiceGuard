import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
from decimal import Decimal
from app.database.base import Base
from app.models import Vendor, PurchaseOrder, PurchaseOrderItem, Invoice, InvoiceItem, Verification, InvoiceException

# Create an in-memory SQLite database for testing, as tests shouldn't hit prod Supabase DB.
# Wait, the instruction says: "Use the existing test infrastructure. Do not create a second database/session system just for these tests."
# Let's import the real engine from app.database.connection or override it.
# However, if I use the real engine, I'll write to the Supabase database.
# The user said: "Use the existing test infrastructure. Do not create a second database/session system just for these tests."
# Let's import get_db and engine from app.database.connection.

from app.database.connection import engine, SessionLocal

# To avoid permanently altering the database, tests can run in a transaction and rollback.

@pytest.fixture(scope="module")
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

def test_vendor_creation(db_session):
    vendor = Vendor(name="Test Vendor", tax_id="TAX123", contact_email="test@vendor.com")
    db_session.add(vendor)
    db_session.commit() # Note: committing flushes to the transaction, but outer transaction will rollback
    
    assert vendor.id is not None
    assert vendor.name == "Test Vendor"

def test_purchase_order_and_items(db_session):
    vendor = Vendor(name="PO Vendor", tax_id="TAX456")
    db_session.add(vendor)
    db_session.flush()

    po = PurchaseOrder(
        po_number="PO-001",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("100.50"),
        status="PENDING"
    )
    db_session.add(po)
    db_session.flush()

    assert po.id is not None
    
    item = PurchaseOrderItem(
        po_id=po.id,
        description="Widget",
        quantity=Decimal("10.000"),
        unit_price=Decimal("10.05"),
        total_price=Decimal("100.50")
    )
    db_session.add(item)
    db_session.flush()

    assert item.id is not None
    assert len(po.items) == 1
    assert po.vendor.name == "PO Vendor"

def test_invoice_and_relationships(db_session):
    vendor = Vendor(name="Inv Vendor", tax_id="TAX789")
    db_session.add(vendor)
    db_session.flush()

    po = PurchaseOrder(
        po_number="PO-002",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("200.00"),
        status="APPROVED"
    )
    db_session.add(po)
    db_session.flush()

    invoice = Invoice(
        invoice_number="INV-001",
        vendor_id=vendor.id,
        po_id=po.id,
        issue_date=date.today(),
        total_amount=Decimal("200.00"),
        status="PENDING"
    )
    db_session.add(invoice)
    db_session.flush()

    assert invoice.id is not None
    assert invoice.vendor_id == vendor.id
    assert invoice.po_id == po.id

    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="Widget",
        quantity=Decimal("10.000"),
        unit_price=Decimal("20.00"),
        total_price=Decimal("200.00")
    )
    db_session.add(inv_item)
    db_session.flush()
    
    assert len(invoice.items) == 1

def test_verification_and_exceptions(db_session):
    vendor = Vendor(name="Verify Vendor", tax_id="TAX000")
    db_session.add(vendor)
    db_session.flush()

    invoice = Invoice(
        invoice_number="INV-002",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("500.00"),
        status="PENDING"
    )
    db_session.add(invoice)
    db_session.flush()

    verification = Verification(
        invoice_id=invoice.id,
        status="FAILED"
    )
    db_session.add(verification)
    db_session.flush()

    assert verification.id is not None

    exception = InvoiceException(
        verification_id=verification.id,
        exception_type="PRICE_MISMATCH",
        description="Price is too high"
    )
    db_session.add(exception)
    db_session.flush()

    assert len(verification.exceptions) == 1
    assert invoice.verification.id == verification.id

def test_duplicate_po_number_rejection(db_session):
    vendor = Vendor(name="Dup PO Vendor", tax_id="TAX999")
    db_session.add(vendor)
    db_session.flush()

    po1 = PurchaseOrder(po_number="DUP-PO", vendor_id=vendor.id, issue_date=date.today(), total_amount=Decimal("100"), status="PENDING")
    db_session.add(po1)
    db_session.flush()

    po2 = PurchaseOrder(po_number="DUP-PO", vendor_id=vendor.id, issue_date=date.today(), total_amount=Decimal("200"), status="PENDING")
    db_session.add(po2)
    
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

def test_duplicate_invoice_number_for_same_vendor(db_session):
    vendor = Vendor(name="Dup Inv Vendor", tax_id="TAX888")
    db_session.add(vendor)
    db_session.flush()

    inv1 = Invoice(invoice_number="DUP-INV", vendor_id=vendor.id, issue_date=date.today(), total_amount=Decimal("100"), status="PENDING")
    db_session.add(inv1)
    db_session.flush()

    inv2 = Invoice(invoice_number="DUP-INV", vendor_id=vendor.id, issue_date=date.today(), total_amount=Decimal("200"), status="PENDING")
    db_session.add(inv2)
    
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

def test_same_invoice_number_different_vendors(db_session):
    vendor1 = Vendor(name="V1", tax_id="T1")
    vendor2 = Vendor(name="V2", tax_id="T2")
    db_session.add_all([vendor1, vendor2])
    db_session.flush()

    inv1 = Invoice(invoice_number="SAME-INV", vendor_id=vendor1.id, issue_date=date.today(), total_amount=Decimal("100"), status="PENDING")
    inv2 = Invoice(invoice_number="SAME-INV", vendor_id=vendor2.id, issue_date=date.today(), total_amount=Decimal("200"), status="PENDING")
    
    db_session.add_all([inv1, inv2])
    db_session.flush() # Should succeed
    
    assert inv1.id is not None
    assert inv2.id is not None
