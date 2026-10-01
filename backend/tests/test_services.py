import pytest
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from app.schemas.vendor import VendorCreate, VendorUpdate
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderItemCreate
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate, InvoiceItemCreate
from app.services import vendor as vendor_service
from app.services import purchase_order as po_service
from app.services import invoice as invoice_service
from app.models.invoice import InvoiceStatus
from app.database.connection import engine, SessionLocal

@pytest.fixture(scope="module")
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

def test_create_and_get_vendor(db_session: Session):
    vendor_in = VendorCreate(name="Service Vendor", tax_id="SRV-123", contact_email="service@vendor.com")
    vendor = vendor_service.create_vendor(db_session, vendor_in)
    assert vendor.id is not None
    assert vendor.name == "Service Vendor"

    fetched_vendor = vendor_service.get_vendor(db_session, vendor.id)
    assert fetched_vendor is not None
    assert fetched_vendor.tax_id == "SRV-123"

def test_list_and_update_vendor(db_session: Session):
    vendor_in = VendorCreate(name="List Vendor")
    vendor = vendor_service.create_vendor(db_session, vendor_in)
    
    vendors = vendor_service.list_vendors(db_session, limit=1000)
    assert len(vendors) > 0
    assert any(v.name == "List Vendor" for v in vendors)

    update_in = VendorUpdate(name="Updated Vendor")
    updated = vendor_service.update_vendor(db_session, vendor.id, update_in)
    assert updated.name == "Updated Vendor"

def test_create_and_get_purchase_order(db_session: Session):
    # Setup vendor
    vendor_in = VendorCreate(name="PO Vendor", tax_id="PO-V-123")
    vendor = vendor_service.create_vendor(db_session, vendor_in)
    
    po_in = PurchaseOrderCreate(
        po_number="PO-SVC-001",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("500.00"),
        items=[
            PurchaseOrderItemCreate(description="Item 1", quantity=Decimal("5"), unit_price=Decimal("100"), total_price=Decimal("500"))
        ]
    )
    po = po_service.create_purchase_order(db_session, po_in)
    assert po.id is not None
    assert len(po.items) == 1
    
    fetched_po = po_service.get_purchase_order(db_session, po.id)
    assert fetched_po is not None
    assert fetched_po.po_number == "PO-SVC-001"
    
def test_create_and_update_invoice(db_session: Session):
    # Setup vendor
    vendor_in = VendorCreate(name="INV Vendor", tax_id="INV-V-123")
    vendor = vendor_service.create_vendor(db_session, vendor_in)
    
    invoice_in = InvoiceCreate(
        invoice_number="INV-SVC-001",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("1000.00"),
        items=[
            InvoiceItemCreate(description="Item A", quantity=Decimal("10"), unit_price=Decimal("100"), total_price=Decimal("1000"))
        ]
    )
    invoice = invoice_service.create_invoice(db_session, invoice_in)
    assert invoice.id is not None
    
    update_in = InvoiceUpdate(status=InvoiceStatus.VERIFIED)
    updated = invoice_service.update_invoice(db_session, invoice.id, update_in)
    assert updated.status == InvoiceStatus.VERIFIED

def test_duplicate_vendor_tax_id(db_session: Session):
    vendor_in = VendorCreate(name="Dup Vendor", tax_id="DUP-123")
    vendor_service.create_vendor(db_session, vendor_in)
    
    # Second should fail
    with pytest.raises(vendor_service.VendorAlreadyExistsError):
        vendor_service.create_vendor(db_session, vendor_in)

def test_not_found_errors(db_session: Session):
    with pytest.raises(vendor_service.VendorNotFoundError):
        vendor_service.update_vendor(db_session, 999999, VendorUpdate(name="Oops"))
