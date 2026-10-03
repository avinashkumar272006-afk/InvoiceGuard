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

def test_verify_reverification_preserves_id(db_session: Session):
    inv_id = create_test_data(db_session)
    v1 = verify_invoice(db_session, inv_id)
    v1_id = v1.id
    
    v2 = verify_invoice(db_session, inv_id)
    v2_id = v2.id
    
    assert v1_id == v2_id  # Verification ID must remain stable
    verifications = db_session.query(Verification).filter(Verification.invoice_id == inv_id).all()
    assert len(verifications) == 1

def test_verify_preserves_resolved_state_for_same_exception(db_session: Session):
    inv_id = create_test_data(db_session, no_po=True)
    v1 = verify_invoice(db_session, inv_id)
    assert len(v1.exceptions) == 1
    
    # Mark it as resolved
    exc = v1.exceptions[0]
    exc.resolved = True
    db_session.commit()
    
    # Re-verify without changing anything
    v2 = verify_invoice(db_session, inv_id)
    assert len(v2.exceptions) == 1
    assert v2.exceptions[0].resolved == True

def test_verify_removes_stale_exception(db_session: Session):
    # Start with missing PO
    inv_id = create_test_data(db_session, no_po=True)
    v1 = verify_invoice(db_session, inv_id)
    assert len(v1.exceptions) == 1
    
    # Now link a PO (so the exception should disappear)
    inv = db_session.query(Invoice).filter(Invoice.id == inv_id).first()
    
    # Create a PO
    po_items = [PurchaseOrderItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    vendor = db_session.query(Vendor).filter(Vendor.id == inv.vendor_id).first()
    po = PurchaseOrder(
        po_number=f"PO-{uuid.uuid4().hex[:6]}",
        vendor_id=vendor.id,
        issue_date="2023-10-01",
        total_amount=Decimal("100.00"),
        items=po_items
    )
    db_session.add(po)
    db_session.commit()
    
    inv.po_id = po.id
    db_session.commit()
    
    v2 = verify_invoice(db_session, inv_id)
    assert len(v2.exceptions) == 0
    assert v2.status == VerificationStatus.PASSED

def test_verify_creates_new_exception_unresolved(db_session: Session):
    # Start with matching invoice
    inv_id = create_test_data(db_session)
    v1 = verify_invoice(db_session, inv_id)
    assert len(v1.exceptions) == 0
    
    # Change invoice to create a discrepancy
    inv = db_session.query(Invoice).filter(Invoice.id == inv_id).first()
    inv.total_amount = Decimal("200.00")
    db_session.commit()
    
    v2 = verify_invoice(db_session, inv_id)
    assert len(v2.exceptions) > 0
    # All new exceptions should be unresolved
    for exc in v2.exceptions:
        assert exc.resolved == False
    assert v2.status == VerificationStatus.FAILED

def test_verify_identity_collision(db_session: Session):
    # Create PO with one item
    po_items = [PurchaseOrderItem(description="Laptop", quantity=Decimal("2"), unit_price=Decimal("1000.00"), total_price=Decimal("2000.00"))]
    
    # Create Invoice with TWO identical line items, both with price mismatch
    # (e.g. they billed each laptop on a separate line, but both have the wrong price)
    inv_items = [
        InvoiceItem(description="Laptop", quantity=Decimal("1"), unit_price=Decimal("1200.00"), total_price=Decimal("1200.00")),
        InvoiceItem(description="Laptop", quantity=Decimal("1"), unit_price=Decimal("1200.00"), total_price=Decimal("1200.00"))
    ]
    
    inv_id = create_test_data(db_session, po_total="2000.00", inv_total="2400.00", po_items=po_items, inv_items=inv_items)
    
    verification = verify_invoice(db_session, inv_id)
    
    # We expect a PRICE_MISMATCH for the total, and TWO PRICE_MISMATCH exceptions for the line items (one for each line).
    
    price_mismatch_exceptions = [e for e in verification.exceptions if e.exception_type == ExceptionType.PRICE_MISMATCH]
    
    # We should get 3 PRICE_MISMATCH exceptions total (1 for total amount mismatch, 2 for line items)
    assert len(price_mismatch_exceptions) == 3, "Identity collision caused exception loss!"

def test_verify_resolved_collision(db_session: Session):
    # Create PO with one item
    po_items = [PurchaseOrderItem(description="Laptop", quantity=Decimal("2"), unit_price=Decimal("1000.00"), total_price=Decimal("2000.00"))]
    
    # Create Invoice with TWO identical line items, both with price mismatch
    inv_items = [
        InvoiceItem(description="Laptop", quantity=Decimal("1"), unit_price=Decimal("1200.00"), total_price=Decimal("1200.00")),
        InvoiceItem(description="Laptop", quantity=Decimal("1"), unit_price=Decimal("1200.00"), total_price=Decimal("1200.00"))
    ]
    
    inv_id = create_test_data(db_session, po_total="2000.00", inv_total="2400.00", po_items=po_items, inv_items=inv_items)
    
    # Run first verification
    v1 = verify_invoice(db_session, inv_id)
    price_mismatch_exceptions = [e for e in v1.exceptions if e.exception_type == ExceptionType.PRICE_MISMATCH and e.line_item_id is not None]
    assert len(price_mismatch_exceptions) == 2
    
    # Resolve exception for only item A (the first one)
    exc_a = price_mismatch_exceptions[0]
    exc_b = price_mismatch_exceptions[1]
    
    exc_a.resolved = True
    db_session.commit()
    
    # Rerun verification
    v2 = verify_invoice(db_session, inv_id)
    
    # Reload exceptions
    v2_price_mismatch = [e for e in v2.exceptions if e.exception_type == ExceptionType.PRICE_MISMATCH and e.line_item_id is not None]
    assert len(v2_price_mismatch) == 2
    
    # Verify state preservation by line_item_id
    reloaded_exc_a = next(e for e in v2_price_mismatch if e.line_item_id == exc_a.line_item_id)
    reloaded_exc_b = next(e for e in v2_price_mismatch if e.line_item_id == exc_b.line_item_id)
    
    assert reloaded_exc_a.resolved == True, "Resolved state was lost on re-verification!"
    assert reloaded_exc_b.resolved == False, "Unresolved state was incorrectly modified!"

