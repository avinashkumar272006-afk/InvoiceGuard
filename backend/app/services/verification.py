from sqlalchemy.orm import Session
from app.models.invoice import Invoice
from app.models.purchase_order import PurchaseOrder
from app.models.verification import Verification, InvoiceException, VerificationStatus, ExceptionType

class VerificationServiceError(Exception):
    pass

class InvoiceNotFoundError(Exception):
    pass

def verify_invoice(db: Session, invoice_id: int) -> Verification:
    # 1. Load invoice + invoice items
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise InvoiceNotFoundError(f"Invoice with id {invoice_id} not found.")

    from sqlalchemy import func
    
    # Idempotency: reuse existing verification
    existing_verification = db.query(Verification).filter(Verification.invoice_id == invoice_id).first()
    if existing_verification:
        verification = existing_verification
        verification.verified_at = func.now()
    else:
        verification = Verification(invoice_id=invoice_id, status=VerificationStatus.PENDING)
        db.add(verification)
        db.flush()

    new_exceptions = []

    if not invoice.po_id:
        new_exceptions.append(InvoiceException(
            exception_type=ExceptionType.PO_NOT_FOUND,
            description="Invoice is not associated with any Purchase Order."
        ))
    else:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == invoice.po_id).first()
        if not po:
            new_exceptions.append(InvoiceException(
                exception_type=ExceptionType.PO_NOT_FOUND,
                description=f"Associated Purchase Order with id {invoice.po_id} not found."
            ))
        else:
            # Invoice total validation vs Declared Total
            calculated_invoice_total = sum(item.total_price for item in invoice.items)
            if calculated_invoice_total != invoice.total_amount:
                new_exceptions.append(InvoiceException(
                    exception_type=ExceptionType.MATH_ERROR,
                    description=f"Calculated invoice total ({calculated_invoice_total}) does not match declared total ({invoice.total_amount})."
                ))

            # Invoice total vs PO total
            if invoice.total_amount != po.total_amount:
                new_exceptions.append(InvoiceException(
                    exception_type=ExceptionType.PRICE_MISMATCH,
                    description=f"Invoice total ({invoice.total_amount}) does not match PO total ({po.total_amount})."
                ))
            
            po_items_map = {item.description: item for item in po.items}
            
            for inv_item in invoice.items:
                # Math check on line item
                if inv_item.quantity * inv_item.unit_price != inv_item.total_price:
                    new_exceptions.append(InvoiceException(
                        line_item_id=inv_item.id,
                        exception_type=ExceptionType.MATH_ERROR,
                        description=f"Line item '{inv_item.description}' quantity * unit_price ({inv_item.quantity * inv_item.unit_price}) does not match total_price ({inv_item.total_price})."
                    ))

                if inv_item.description not in po_items_map:
                    new_exceptions.append(InvoiceException(
                        line_item_id=inv_item.id,
                        exception_type=ExceptionType.NOT_ON_PO,
                        description=f"Invoice item '{inv_item.description}' not found on Purchase Order."
                    ))
                else:
                    po_item = po_items_map[inv_item.description]
                    
                    if inv_item.quantity > po_item.quantity:
                        new_exceptions.append(InvoiceException(
                            line_item_id=inv_item.id,
                            exception_type=ExceptionType.QUANTITY_MISMATCH,
                            description=f"Invoice item '{inv_item.description}' quantity ({inv_item.quantity}) exceeds PO quantity ({po_item.quantity})."
                        ))
                        
                    if inv_item.unit_price != po_item.unit_price:
                        new_exceptions.append(InvoiceException(
                            line_item_id=inv_item.id,
                            exception_type=ExceptionType.PRICE_MISMATCH,
                            description=f"Invoice item '{inv_item.description}' unit price ({inv_item.unit_price}) does not match PO unit price ({po_item.unit_price})."
                        ))

    old_exceptions_map = {
        (exc.exception_type, exc.description, exc.line_item_id): exc 
        for exc in verification.exceptions
    }
    
    new_exceptions_map = {
        (exc.exception_type, exc.description, exc.line_item_id): exc 
        for exc in new_exceptions
    }

    # Delete stale exceptions
    for key, old_exc in old_exceptions_map.items():
        if key not in new_exceptions_map:
            db.delete(old_exc)

    # Add new exceptions
    for key, new_exc in new_exceptions_map.items():
        if key not in old_exceptions_map:
            new_exc.verification_id = verification.id
            db.add(new_exc)

    if len(new_exceptions) > 0:
        verification.status = VerificationStatus.FAILED
    else:
        verification.status = VerificationStatus.PASSED
        
    db.commit()
    db.refresh(verification)
    return verification

def get_verification(db: Session, invoice_id: int) -> Verification:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise InvoiceNotFoundError(f"Invoice with id {invoice_id} not found.")
        
    verification = db.query(Verification).filter(Verification.invoice_id == invoice_id).first()
    return verification

def get_exception_summary(db: Session) -> dict:
    from sqlalchemy import func
    
    total = db.query(func.count(InvoiceException.id)).scalar() or 0
    resolved = db.query(func.count(InvoiceException.id)).filter(InvoiceException.resolved == True).scalar() or 0
    unresolved = db.query(func.count(InvoiceException.id)).filter(InvoiceException.resolved == False).scalar() or 0
    
    by_type_query = db.query(
        InvoiceException.exception_type,
        func.count(InvoiceException.id)
    ).group_by(InvoiceException.exception_type).all()
    
    by_type = {exc_type.value: count for exc_type, count in by_type_query}
    
    return {
        "total": total,
        "resolved": resolved,
        "unresolved": unresolved,
        "by_type": by_type
    }
