from decimal import Decimal
import pytest
import uuid
from sqlalchemy.orm import Session

from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.invoice import Invoice, InvoiceItem
from app.models.verification import Verification, VerificationStatus, ExceptionType
from app.models.audit import AuditLog
from app.schemas.invoice import InvoiceLinkPO
from app.services.invoice import link_invoice_to_purchase_order, InvoiceNotFoundError, PurchaseOrderNotFoundError
from app.services.verification import verify_invoice
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

def create_test_vendor_po_inv(db: Session, has_po=False):
    suffix = uuid.uuid4().hex[:6]
    vendor = Vendor(name="Link Vendor", tax_id=f"TAX-L-{suffix}", contact_email="testlink@vendor.com")
    db.add(vendor)
    db.flush()
    
    po = PurchaseOrder(
        po_number=f"PO-L-{suffix}",
        vendor_id=vendor.id,
        issue_date="2023-10-01",
        total_amount=Decimal("100.00"),
        items=[PurchaseOrderItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    )
    db.add(po)
    db.flush()
    
    po_id = po.id if has_po else None
    
    inv = Invoice(
        invoice_number=f"INV-L-{suffix}",
        vendor_id=vendor.id,
        po_id=po_id,
        issue_date="2023-10-05",
        total_amount=Decimal("100.00"),
        items=[InvoiceItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    )
    db.add(inv)
    db.commit()
    
    return vendor.id, po.id, inv.id

def test_successful_po_link(db_session: Session):
    vendor_id, po_id, inv_id = create_test_vendor_po_inv(db_session, has_po=False)
    
    # Pre-link verification should fail with PO_NOT_FOUND
    v1 = verify_invoice(db_session, inv_id)
    assert ExceptionType.PO_NOT_FOUND in [e.exception_type for e in v1.exceptions]
    
    data = InvoiceLinkPO(po_id=po_id, actor="reviewer@test.com", comment="Matching PO")
    
    # Perform link
    updated_inv = link_invoice_to_purchase_order(db_session, inv_id, data)
    assert updated_inv.po_id == po_id
    
    # Verify AuditLog created
    logs = db_session.query(AuditLog).filter(AuditLog.invoice_id == inv_id).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.action == "PO_LINKED"
    assert log.actor == "reviewer@test.com"
    assert log.previous_state == "PO: None"
    assert log.new_state == f"PO: {po_id}"
    
    # Post-link verification should be updated
    v2 = db_session.query(Verification).filter(Verification.invoice_id == inv_id).first()
    assert v2.status == VerificationStatus.PASSED
    assert ExceptionType.PO_NOT_FOUND not in [e.exception_type for e in v2.exceptions]

def test_missing_invoice_link(db_session: Session):
    data = InvoiceLinkPO(po_id=1, actor="test@test.com")
    with pytest.raises(InvoiceNotFoundError):
        link_invoice_to_purchase_order(db_session, 999999, data)

def test_missing_po_link(db_session: Session):
    vendor_id, po_id, inv_id = create_test_vendor_po_inv(db_session, has_po=False)
    data = InvoiceLinkPO(po_id=999999, actor="test@test.com")
    with pytest.raises(PurchaseOrderNotFoundError):
        link_invoice_to_purchase_order(db_session, inv_id, data)

def test_relink_behavior(db_session: Session):
    vendor_id, po_id_1, inv_id = create_test_vendor_po_inv(db_session, has_po=True)
    
    # Create a second PO
    po_2 = PurchaseOrder(
        po_number=f"PO-L2-{uuid.uuid4().hex[:6]}",
        vendor_id=vendor_id,
        issue_date="2023-10-01",
        total_amount=Decimal("120.00"),
        items=[PurchaseOrderItem(description="Item A", quantity=Decimal("12"), unit_price=Decimal("10.00"), total_price=Decimal("120.00"))]
    )
    db_session.add(po_2)
    db_session.commit()
    po_id_2 = po_2.id
    
    # Ensure current is po_1
    inv = db_session.query(Invoice).filter(Invoice.id == inv_id).first()
    assert inv.po_id == po_id_1
    
    # Link to po_2
    data = InvoiceLinkPO(po_id=po_id_2, actor="relink@test.com")
    link_invoice_to_purchase_order(db_session, inv_id, data)
    
    # Verify AuditLog has previous_state PO: id1
    logs = db_session.query(AuditLog).filter(AuditLog.invoice_id == inv_id).order_by(AuditLog.created_at.desc()).all()
    # It might have other logs from initial verification if any, but we just check the latest
    latest_log = logs[0]
    assert latest_log.action == "PO_LINKED"
    assert latest_log.previous_state == f"PO: {po_id_1}"
    assert latest_log.new_state == f"PO: {po_id_2}"
    
    # Verify verification updated to reflect mismatch
    v2 = db_session.query(Verification).filter(Verification.invoice_id == inv_id).first()
    exc_types = [e.exception_type for e in v2.exceptions]
    assert ExceptionType.PRICE_MISMATCH in exc_types
    # QUANTITY_MISMATCH only happens if inv > po, which is 10 > 8. Let's assume we don't need to check qty mismatch here, or we can check it's NOT there.
    assert ExceptionType.QUANTITY_MISMATCH not in exc_types

def test_actual_po_mismatch_detection_after_link(db_session: Session):
    vendor_id, po_id, inv_id = create_test_vendor_po_inv(db_session, has_po=False)
    
    # Modify invoice to have quantity mismatch
    inv_item = db_session.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv_id).first()
    inv_item.quantity = Decimal("15")
    db_session.commit()
    
    data = InvoiceLinkPO(po_id=po_id, actor="test@test.com")
    link_invoice_to_purchase_order(db_session, inv_id, data)
    
    v = db_session.query(Verification).filter(Verification.invoice_id == inv_id).first()
    exc_types = [e.exception_type for e in v.exceptions]
    assert ExceptionType.QUANTITY_MISMATCH in exc_types
    
def test_resolved_exception_preservation_after_relink(db_session: Session):
    vendor_id, po_id_1, inv_id = create_test_vendor_po_inv(db_session, has_po=True)
    
    # Ensure a math error exists on invoice level
    inv = db_session.query(Invoice).filter(Invoice.id == inv_id).first()
    inv.total_amount = Decimal("999.99")
    db_session.commit()
    
    # Verify once to create MATH_ERROR
    v1 = verify_invoice(db_session, inv_id)
    math_exc = next(e for e in v1.exceptions if e.exception_type == ExceptionType.MATH_ERROR)
    
    # Resolve the exception
    math_exc.resolved = True
    db_session.commit()
    
    # Create a second PO
    po_2 = PurchaseOrder(
        po_number=f"PO-L3-{uuid.uuid4().hex[:6]}",
        vendor_id=vendor_id,
        issue_date="2023-10-01",
        total_amount=Decimal("100.00"),
        items=[PurchaseOrderItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    )
    db_session.add(po_2)
    db_session.commit()
    
    # Now link to second PO
    data = InvoiceLinkPO(po_id=po_2.id, actor="test@test.com")
    link_invoice_to_purchase_order(db_session, inv_id, data)
    
    # Re-fetch verification
    v2 = db_session.query(Verification).filter(Verification.invoice_id == inv_id).first()
    math_exc_again = next(e for e in v2.exceptions if e.exception_type == ExceptionType.MATH_ERROR)
    
    # Should still be resolved!
    assert math_exc_again.resolved == True

def test_same_po_relink(db_session: Session):
    vendor_id, po_id, inv_id = create_test_vendor_po_inv(db_session, has_po=True)
    
    # ensure it's linked
    inv = db_session.query(Invoice).filter(Invoice.id == inv_id).first()
    assert inv.po_id == po_id
    
    data = InvoiceLinkPO(po_id=po_id, actor="same@test.com")
    link_invoice_to_purchase_order(db_session, inv_id, data)
    
    # check audit log
    log = db_session.query(AuditLog).filter(AuditLog.invoice_id == inv_id).order_by(AuditLog.created_at.desc()).first()
    assert log.action == "PO_LINKED"
    assert log.previous_state == f"PO: {po_id}"
    assert log.new_state == f"PO: {po_id}"
    
    # verify
    v = db_session.query(Verification).filter(Verification.invoice_id == inv_id).first()
    assert v.status == VerificationStatus.PASSED

def test_failed_link_no_audit(db_session: Session):
    vendor_id, po_id, inv_id = create_test_vendor_po_inv(db_session, has_po=False)
    
    # Try to link to a missing PO
    data = InvoiceLinkPO(po_id=999999, actor="fail@test.com")
    with pytest.raises(PurchaseOrderNotFoundError):
        link_invoice_to_purchase_order(db_session, inv_id, data)
    
    # No audit log should be created
    logs = db_session.query(AuditLog).filter(AuditLog.invoice_id == inv_id, AuditLog.actor == "fail@test.com").all()
    assert len(logs) == 0
    
    # po_id should remain None
    inv = db_session.query(Invoice).filter(Invoice.id == inv_id).first()
    assert inv.po_id is None

from unittest.mock import patch

def test_transaction_safety_on_verification_failure(db_session: Session):
    vendor_id, po_id, inv_id = create_test_vendor_po_inv(db_session, has_po=False)
    
    data = InvoiceLinkPO(po_id=po_id, actor="trans@test.com")
    
    # Mock verify_invoice to raise an exception
    with patch('app.services.invoice.verify_invoice') as mock_verify:
        mock_verify.side_effect = Exception("Verification failed horribly")
        
        try:
            # Create a savepoint
            with db_session.begin_nested():
                link_invoice_to_purchase_order(db_session, inv_id, data)
        except Exception as e:
            assert str(e) == "Verification failed horribly"
            
    # The session rolled back to the savepoint automatically because of begin_nested()
    # Now check the DB
    inv = db_session.query(Invoice).filter(Invoice.id == inv_id).first()
    assert inv.po_id is None
    logs = db_session.query(AuditLog).filter(AuditLog.invoice_id == inv_id, AuditLog.actor == "trans@test.com").all()
    assert len(logs) == 0

def test_exception_lifecycle_unrelated_new_exceptions(db_session: Session):
    vendor_id, po_id_1, inv_id = create_test_vendor_po_inv(db_session, has_po=True)
    
    # Let's change Invoice to have qty=15 (creates QUANTITY_MISMATCH against PO 1)
    inv_item = db_session.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv_id).first()
    inv_item.quantity = Decimal("15")
    db_session.commit()
    
    verify_invoice(db_session, inv_id)
    v1 = db_session.query(Verification).filter(Verification.invoice_id == inv_id).first()
    
    qty_exc = next(e for e in v1.exceptions if e.exception_type == ExceptionType.QUANTITY_MISMATCH)
    qty_exc.resolved = True
    db_session.commit()
    
    # Create PO 2 which has qty=15, but unit_price=5.00
    po_2 = PurchaseOrder(
        po_number=f"PO-L4-{uuid.uuid4().hex[:6]}",
        vendor_id=vendor_id,
        issue_date="2023-10-01",
        total_amount=Decimal("75.00"),
        items=[PurchaseOrderItem(description="Item A", quantity=Decimal("15"), unit_price=Decimal("5.00"), total_price=Decimal("75.00"))]
    )
    db_session.add(po_2)
    db_session.commit()
    
    # Relink to PO 2
    data = InvoiceLinkPO(po_id=po_2.id, actor="relink2@test.com")
    link_invoice_to_purchase_order(db_session, inv_id, data)
    
    v2 = db_session.query(Verification).filter(Verification.invoice_id == inv_id).first()
    exc_types = [e.exception_type for e in v2.exceptions]
    
    # Exception X (QUANTITY_MISMATCH) should be removed because 15 == 15
    assert ExceptionType.QUANTITY_MISMATCH not in exc_types
    # New exception (PRICE_MISMATCH) should be present and unresolved
    assert ExceptionType.PRICE_MISMATCH in exc_types
    
    price_exc = next(e for e in v2.exceptions if e.exception_type == ExceptionType.PRICE_MISMATCH)
    assert price_exc.resolved == False
