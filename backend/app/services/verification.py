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

    if not invoice.vendor_id:
        if invoice.vendor_name_raw:
            desc = f"Invoice vendor '{invoice.vendor_name_raw}' could not be resolved."
        else:
            desc = "Invoice vendor could not be resolved."
        new_exceptions.append(InvoiceException(
            exception_type=ExceptionType.VENDOR_UNRESOLVED,
            description=desc
        ))

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
            
            import re
            def normalize_desc(desc: str) -> str:
                if not desc:
                    return ""
                desc = desc.strip().lower()
                desc = re.sub(r'[^a-z0-9]', '', desc)
                return desc

            po_items_by_id = {item.id: item for item in po.items}
            po_items_exact = {}
            for po_item in po.items:
                desc = po_item.description
                if desc in po_items_exact:
                    po_items_exact[desc] = None # Ambiguous
                else:
                    po_items_exact[desc] = po_item
            po_items_norm = {}
            for po_item in po.items:
                norm = normalize_desc(po_item.description)
                if norm in po_items_norm:
                    po_items_norm[norm] = None # Ambiguous
                else:
                    po_items_norm[norm] = po_item
            
            aggregated_quantities = {} # {po_item_id: [inv_item1, inv_item2]}
            
            for inv_item in invoice.items:
                # Math check on line item
                if inv_item.quantity * inv_item.unit_price != inv_item.total_price:
                    new_exceptions.append(InvoiceException(
                        line_item_id=inv_item.id,
                        exception_type=ExceptionType.MATH_ERROR,
                        description=f"Line item '{inv_item.description}' quantity * unit_price ({inv_item.quantity * inv_item.unit_price}) does not match total_price ({inv_item.total_price})."
                    ))

                matched_po_item = None
                
                # Rule 1: po_item_id is authoritative
                if inv_item.po_item_id is not None:
                    matched_po_item = po_items_by_id.get(inv_item.po_item_id)
                else:
                    # Rule 2: exact match
                    if inv_item.description in po_items_exact:
                        matched_po_item = po_items_exact[inv_item.description]
                    else:
                        # Rule 3: normalized match
                        norm_desc = normalize_desc(inv_item.description)
                        matched_po_item = po_items_norm.get(norm_desc)

                if not matched_po_item:
                    new_exceptions.append(InvoiceException(
                        line_item_id=inv_item.id,
                        exception_type=ExceptionType.NOT_ON_PO,
                        description=f"Invoice item '{inv_item.description}' not found on Purchase Order."
                    ))
                else:
                    po_item = matched_po_item
                    
                    if po_item.id not in aggregated_quantities:
                        aggregated_quantities[po_item.id] = []
                    aggregated_quantities[po_item.id].append(inv_item)
                        
                    if inv_item.unit_price != po_item.unit_price:
                        new_exceptions.append(InvoiceException(
                            line_item_id=inv_item.id,
                            exception_type=ExceptionType.PRICE_MISMATCH,
                            description=f"Invoice item '{inv_item.description}' unit price ({inv_item.unit_price}) does not match PO unit price ({po_item.unit_price})."
                        ))

            # Rule 7 & 8: Quantity validation
            for po_item_id, inv_items in aggregated_quantities.items():
                po_item = po_items_by_id[po_item_id]
                total_inv_qty = sum(item.quantity for item in inv_items)
                
                if total_inv_qty > po_item.quantity:
                    primary_inv_item = sorted(inv_items, key=lambda x: x.id)[0]
                    
                    if len(inv_items) > 1:
                        desc = f"Aggregated invoice quantity ({total_inv_qty}) for PO item '{po_item.description}' exceeds PO quantity ({po_item.quantity})."
                    else:
                        desc = f"Invoice item '{primary_inv_item.description}' quantity ({total_inv_qty}) exceeds PO quantity ({po_item.quantity})."
                        
                    new_exceptions.append(InvoiceException(
                        line_item_id=primary_inv_item.id,
                        exception_type=ExceptionType.QUANTITY_MISMATCH,
                        description=desc
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
