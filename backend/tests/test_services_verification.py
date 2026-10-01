from decimal import Decimal
import pytest
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.invoice import Invoice, InvoiceItem
from app.models.verification import Verification, VerificationStatus, ExceptionType
from app.services.verification import verify_invoice, get_verification, InvoiceNotFoundError
from sqlalchemy.orm import Session
import uuid
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

def create_test_data(db: Session, po_total="100.00", inv_total="100.00", po_items=None, inv_items=None, no_po=False):
    # Unique suffix
    suffix = uuid.uuid4().hex[:6]
    
    vendor = Vendor(name="Verify Vendor", tax_id=f"TAX-{suffix}", contact_email="test@vendor.com")
    db.add(vendor)
    db.flush()
    
    if po_items is None:
        po_items = [PurchaseOrderItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    
    if inv_items is None:
        inv_items = [InvoiceItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
        
    po = PurchaseOrder(
        po_number=f"PO-{suffix}",
        vendor_id=vendor.id,
        issue_date="2023-10-01",
        total_amount=Decimal(po_total),
        items=po_items
    )
    db.add(po)
    db.flush()
    
    inv = Invoice(
        invoice_number=f"INV-{suffix}",
        vendor_id=vendor.id,
        po_id=po.id if not no_po else None,
        issue_date="2023-10-05",
        total_amount=Decimal(inv_total),
        items=inv_items
    )
    db.add(inv)
    db.commit()
    return inv.id

def test_verify_exact_match(db_session: Session):
    inv_id = create_test_data(db_session)
    verification = verify_invoice(db_session, inv_id)
    assert verification.status == VerificationStatus.PASSED
    assert len(verification.exceptions) == 0

def test_verify_missing_po(db_session: Session):
    inv_id = create_test_data(db_session, no_po=True)
    verification = verify_invoice(db_session, inv_id)
    assert verification.status == VerificationStatus.FAILED
    assert len(verification.exceptions) == 1
    assert verification.exceptions[0].exception_type == ExceptionType.PO_NOT_FOUND

def test_verify_price_mismatch(db_session: Session):
    po_items = [PurchaseOrderItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    inv_items = [InvoiceItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("12.00"), total_price=Decimal("120.00"))]
    
    inv_id = create_test_data(db_session, po_total="100.00", inv_total="120.00", po_items=po_items, inv_items=inv_items)
    verification = verify_invoice(db_session, inv_id)
    assert verification.status == VerificationStatus.FAILED
    
    exc_types = [e.exception_type for e in verification.exceptions]
    assert ExceptionType.PRICE_MISMATCH in exc_types  # Total amount mismatch
    # It might also have PRICE_MISMATCH for line item

def test_verify_quantity_mismatch(db_session: Session):
    po_items = [PurchaseOrderItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    inv_items = [InvoiceItem(description="Item A", quantity=Decimal("12"), unit_price=Decimal("10.00"), total_price=Decimal("120.00"))]
    
    inv_id = create_test_data(db_session, po_total="100.00", inv_total="120.00", po_items=po_items, inv_items=inv_items)
    verification = verify_invoice(db_session, inv_id)
    assert verification.status == VerificationStatus.FAILED
    
    exc_types = [e.exception_type for e in verification.exceptions]
    assert ExceptionType.QUANTITY_MISMATCH in exc_types

def test_verify_math_error(db_session: Session):
    # Declared total is 100, but 10 * 10 = 100. Wait, inv_items total is 100, but declared is 150.
    po_items = [PurchaseOrderItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    inv_items = [InvoiceItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    
    inv_id = create_test_data(db_session, po_total="100.00", inv_total="150.00", po_items=po_items, inv_items=inv_items)
    verification = verify_invoice(db_session, inv_id)
    
    exc_types = [e.exception_type for e in verification.exceptions]
    assert ExceptionType.MATH_ERROR in exc_types
    assert ExceptionType.PRICE_MISMATCH in exc_types

def test_verify_unmatched_item(db_session: Session):
    po_items = [PurchaseOrderItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    inv_items = [
        InvoiceItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00")),
        InvoiceItem(description="Item B (Extra)", quantity=Decimal("5"), unit_price=Decimal("10.00"), total_price=Decimal("50.00"))
    ]
    
    inv_id = create_test_data(db_session, po_total="100.00", inv_total="150.00", po_items=po_items, inv_items=inv_items)
    verification = verify_invoice(db_session, inv_id)
    
    exc_types = [e.exception_type for e in verification.exceptions]
    assert ExceptionType.NOT_ON_PO in exc_types

def test_verify_idempotency(db_session: Session):
    inv_id = create_test_data(db_session)
    v1 = verify_invoice(db_session, inv_id)
    v1_id = v1.id
    
    v2 = verify_invoice(db_session, inv_id)
    v2_id = v2.id
    
    assert v1_id != v2_id  # It should create a new one and delete the old one
    # Verify we don't have multiple verifications
    verifications = db_session.query(Verification).filter(Verification.invoice_id == inv_id).all()
    assert len(verifications) == 1
