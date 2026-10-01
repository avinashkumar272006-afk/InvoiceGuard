from decimal import Decimal
import pytest
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.verification import Verification, VerificationStatus, ExceptionType, InvoiceException
from app.services.review import resolve_exception, review_invoice, get_audit_logs, InvalidStateTransitionError
from app.schemas.audit import ReviewCreate, ExceptionResolveCreate
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

def create_test_data(db: Session, add_exception=False):
    suffix = uuid.uuid4().hex[:6]
    vendor = Vendor(name="Review Vendor", tax_id=f"TAX-REV-{suffix}", contact_email="test@vendor.com")
    db.add(vendor)
    db.flush()
    
    po = PurchaseOrder(
        po_number=f"PO-REV-{suffix}",
        vendor_id=vendor.id,
        issue_date="2023-10-01",
        total_amount=Decimal("100.00"),
        items=[PurchaseOrderItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    )
    db.add(po)
    db.flush()
    
    inv = Invoice(
        invoice_number=f"INV-REV-{suffix}",
        vendor_id=vendor.id,
        po_id=po.id,
        issue_date="2023-10-05",
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.PENDING,
        items=[InvoiceItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    )
    db.add(inv)
    db.flush()

    ver = Verification(
        invoice_id=inv.id,
        status=VerificationStatus.FAILED if add_exception else VerificationStatus.PASSED
    )
    db.add(ver)
    db.flush()

    if add_exception:
        exc = InvoiceException(
            verification_id=ver.id,
            exception_type=ExceptionType.PRICE_MISMATCH,
            description="Price mismatch test"
        )
        db.add(exc)
        db.flush()

    db.commit()
    db.refresh(inv)
    return inv.id

def test_resolve_exception(db_session: Session):
    inv_id = create_test_data(db_session, add_exception=True)
    inv = db_session.query(Invoice).filter_by(id=inv_id).first()
    exc_id = inv.verification.exceptions[0].id

    req = ExceptionResolveCreate(actor="user1", comment="OK")
    exc = resolve_exception(db_session, inv_id, exc_id, req)
    
    assert exc.resolved is True
    
    # Audit log check
    logs = get_audit_logs(db_session, inv_id)
    assert len(logs) == 1
    assert logs[0].action == "EXCEPTION_RESOLVED"
    assert logs[0].actor == "user1"
    assert logs[0].entity_id == exc_id

    # Try resolving again -> error
    with pytest.raises(InvalidStateTransitionError):
        resolve_exception(db_session, inv_id, exc_id, req)

def test_verify_invoice_no_exception(db_session: Session):
    inv_id = create_test_data(db_session, add_exception=False)
    req = ReviewCreate(status="VERIFIED", actor="user2")
    inv = review_invoice(db_session, inv_id, req)
    
    assert inv.status == InvoiceStatus.VERIFIED
    
    logs = get_audit_logs(db_session, inv_id)
    assert len(logs) == 1
    assert logs[0].action == "STATUS_CHANGE"
    assert logs[0].new_state == "VERIFIED"

def test_verify_invoice_unresolved_exception(db_session: Session):
    inv_id = create_test_data(db_session, add_exception=True)
    req = ReviewCreate(status="VERIFIED", actor="user3")
    
    with pytest.raises(InvalidStateTransitionError) as e:
        review_invoice(db_session, inv_id, req)
    assert "unresolved exceptions" in str(e.value)

def test_verify_invoice_resolved_exception(db_session: Session):
    inv_id = create_test_data(db_session, add_exception=True)
    inv = db_session.query(Invoice).filter_by(id=inv_id).first()
    exc_id = inv.verification.exceptions[0].id

    resolve_req = ExceptionResolveCreate(actor="user4")
    resolve_exception(db_session, inv_id, exc_id, resolve_req)
    
    req = ReviewCreate(status="VERIFIED", actor="user4", comment="All resolved")
    inv = review_invoice(db_session, inv_id, req)
    
    assert inv.status == InvoiceStatus.VERIFIED

def test_dispute_invoice(db_session: Session):
    inv_id = create_test_data(db_session, add_exception=True)
    req = ReviewCreate(status="DISPUTED", actor="user5")
    inv = review_invoice(db_session, inv_id, req)
    
    assert inv.status == InvoiceStatus.DISPUTED

def test_invalid_state_transition(db_session: Session):
    inv_id = create_test_data(db_session, add_exception=False)
    # Set to verified
    review_invoice(db_session, inv_id, ReviewCreate(status="VERIFIED", actor="user6"))
    
    # Try to verify again -> error
    with pytest.raises(InvalidStateTransitionError):
        review_invoice(db_session, inv_id, ReviewCreate(status="DISPUTED", actor="user7"))
