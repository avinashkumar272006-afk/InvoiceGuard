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

    # Idempotency: remove existing verification
    existing_verification = db.query(Verification).filter(Verification.invoice_id == invoice_id).first()
    if existing_verification:
        db.delete(existing_verification)
        db.flush()

    verification = Verification(invoice_id=invoice_id, status=VerificationStatus.PENDING)
    exceptions = []

    if not invoice.po_id:
        exceptions.append(InvoiceException(
            exception_type=ExceptionType.PO_NOT_FOUND,
            description="Invoice is not associated with any Purchase Order."
        ))
        verification.status = VerificationStatus.FAILED
    else:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == invoice.po_id).first()
        if not po:
            exceptions.append(InvoiceException(
                exception_type=ExceptionType.PO_NOT_FOUND,
                description=f"Associated Purchase Order with id {invoice.po_id} not found."
            ))
            verification.status = VerificationStatus.FAILED
        else:
            # Invoice total validation vs Declared Total
            calculated_invoice_total = sum(item.total_price for item in invoice.items)
            if calculated_invoice_total != invoice.total_amount:
                exceptions.append(InvoiceException(
                    exception_type=ExceptionType.MATH_ERROR,
                    description=f"Calculated invoice total ({calculated_invoice_total}) does not match declared total ({invoice.total_amount})."
                ))

            # Invoice total vs PO total
            if invoice.total_amount != po.total_amount:
                exceptions.append(InvoiceException(
                    exception_type=ExceptionType.PRICE_MISMATCH,
                    description=f"Invoice total ({invoice.total_amount}) does not match PO total ({po.total_amount})."
                ))
            
            po_items_map = {item.description: item for item in po.items}
            
            for inv_item in invoice.items:
                # Math check on line item
                if inv_item.quantity * inv_item.unit_price != inv_item.total_price:
                    exceptions.append(InvoiceException(
                        exception_type=ExceptionType.MATH_ERROR,
                        description=f"Line item '{inv_item.description}' quantity * unit_price ({inv_item.quantity * inv_item.unit_price}) does not match total_price ({inv_item.total_price})."
                    ))

                if inv_item.description not in po_items_map:
                    exceptions.append(InvoiceException(
                        exception_type=ExceptionType.NOT_ON_PO,
                        description=f"Invoice item '{inv_item.description}' not found on Purchase Order."
                    ))
                else:
                    po_item = po_items_map[inv_item.description]
                    
                    if inv_item.quantity > po_item.quantity:
                        exceptions.append(InvoiceException(
                            exception_type=ExceptionType.QUANTITY_MISMATCH,
                            description=f"Invoice item '{inv_item.description}' quantity ({inv_item.quantity}) exceeds PO quantity ({po_item.quantity})."
                        ))
                        
                    if inv_item.unit_price != po_item.unit_price:
                        exceptions.append(InvoiceException(
                            exception_type=ExceptionType.PRICE_MISMATCH,
                            description=f"Invoice item '{inv_item.description}' unit price ({inv_item.unit_price}) does not match PO unit price ({po_item.unit_price})."
                        ))

            if len(exceptions) > 0:
                verification.status = VerificationStatus.FAILED
            else:
                verification.status = VerificationStatus.PASSED

    db.add(verification)
    db.flush()

    for exc in exceptions:
        exc.verification_id = verification.id
        db.add(exc)
        
    db.commit()
    db.refresh(verification)
    return verification

def get_verification(db: Session, invoice_id: int) -> Verification:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise InvoiceNotFoundError(f"Invoice with id {invoice_id} not found.")
        
    verification = db.query(Verification).filter(Verification.invoice_id == invoice_id).first()
    return verification
