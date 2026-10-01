from sqlalchemy.orm import Session
from app.models.invoice import Invoice, InvoiceStatus
from app.models.verification import Verification, InvoiceException, VerificationStatus
from app.models.audit import AuditLog
from app.schemas.audit import ReviewCreate, ExceptionResolveCreate
from typing import List

class ReviewError(Exception):
    pass

class InvoiceNotFoundError(ReviewError):
    pass

class ExceptionNotFoundError(ReviewError):
    pass

class InvalidStateTransitionError(ReviewError):
    pass

def resolve_exception(db: Session, invoice_id: int, exception_id: int, data: ExceptionResolveCreate) -> InvoiceException:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise InvoiceNotFoundError(f"Invoice {invoice_id} not found.")

    exc = db.query(InvoiceException).join(Verification).filter(
        Verification.invoice_id == invoice_id,
        InvoiceException.id == exception_id
    ).first()
    
    if not exc:
        raise ExceptionNotFoundError(f"Exception {exception_id} not found or doesn't belong to invoice {invoice_id}.")
        
    if exc.resolved:
        raise InvalidStateTransitionError(f"Exception {exception_id} is already resolved.")
        
    exc.resolved = True
    
    audit = AuditLog(
        invoice_id=invoice_id,
        actor=data.actor,
        action="EXCEPTION_RESOLVED",
        entity_name="EXCEPTION",
        entity_id=exc.id,
        comment=data.comment
    )
    db.add(audit)
    db.commit()
    db.refresh(exc)
    return exc

def review_invoice(db: Session, invoice_id: int, data: ReviewCreate) -> Invoice:
    if data.status not in [InvoiceStatus.VERIFIED, InvoiceStatus.DISPUTED]:
        raise InvalidStateTransitionError(f"Status must be VERIFIED or DISPUTED, got {data.status}")

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise InvoiceNotFoundError(f"Invoice {invoice_id} not found.")
        
    if invoice.status != InvoiceStatus.PENDING:
        raise InvalidStateTransitionError(f"Cannot review invoice in {invoice.status.value} state. Must be PENDING.")

    if data.status == InvoiceStatus.VERIFIED:
        verification = db.query(Verification).filter(Verification.invoice_id == invoice_id).first()
        if not verification:
            raise InvalidStateTransitionError("Cannot verify invoice without a Verification record.")
            
        unresolved = [e for e in verification.exceptions if not e.resolved]
        if unresolved:
            raise InvalidStateTransitionError(f"Cannot verify invoice with {len(unresolved)} unresolved exceptions.")

    old_status = invoice.status.value
    invoice.status = InvoiceStatus[data.status]
    
    audit = AuditLog(
        invoice_id=invoice_id,
        actor=data.actor,
        action="STATUS_CHANGE",
        entity_name="INVOICE",
        entity_id=invoice.id,
        previous_state=old_status,
        new_state=invoice.status.value,
        comment=data.comment
    )
    db.add(audit)
    db.commit()
    db.refresh(invoice)
    return invoice

def get_audit_logs(db: Session, invoice_id: int) -> List[AuditLog]:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise InvoiceNotFoundError(f"Invoice {invoice_id} not found.")
        
    logs = db.query(AuditLog).filter(AuditLog.invoice_id == invoice_id).order_by(AuditLog.created_at.desc()).all()
    return logs
