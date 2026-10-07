from typing import List, Optional
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from app.models.invoice import Invoice, InvoiceItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.audit import AuditLog
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate, InvoiceLinkPO, InvoiceLinkVendor, InvoiceItemMapPO, InvoiceItemUnmapPO
from app.services.verification import verify_invoice

class InvoiceNotFoundError(Exception):
    pass

class InvoiceAlreadyExistsError(Exception):
    pass

class PurchaseOrderNotFoundError(Exception):
    pass

class InvoiceItemNotFoundError(Exception):
    pass

class PurchaseOrderItemNotFoundError(Exception):
    pass

class InvoiceNotLinkedToPOError(Exception):
    pass

class POItemBelongsToAnotherPOError(Exception):
    pass

def create_invoice(db: Session, invoice_in: InvoiceCreate) -> Invoice:
    invoice_data = invoice_in.model_dump(exclude={"items"})
    db_invoice = Invoice(**invoice_data)
    
    for item_in in invoice_in.items:
        db_item = InvoiceItem(**item_in.model_dump())
        db_invoice.items.append(db_item)
        
    db.add(db_invoice)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise InvoiceAlreadyExistsError("Invoice with this number already exists for the given vendor.")
    return db_invoice

def get_invoice(db: Session, invoice_id: int) -> Optional[Invoice]:
    return db.query(Invoice).options(selectinload(Invoice.document)).filter(Invoice.id == invoice_id).first()

def list_invoices(db: Session, skip: int = 0, limit: int = 100) -> List[Invoice]:
    return db.query(Invoice).options(selectinload(Invoice.document)).offset(skip).limit(limit).all()

def update_invoice(db: Session, invoice_id: int, invoice_in: InvoiceUpdate) -> Invoice:
    db_invoice = get_invoice(db, invoice_id)
    if not db_invoice:
        raise InvoiceNotFoundError(f"Invoice with id {invoice_id} not found.")
    
    update_data = invoice_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_invoice, key, value)
        
    db.flush()
    return db_invoice

def link_invoice_to_purchase_order(db: Session, invoice_id: int, data: InvoiceLinkPO) -> Invoice:
    db_invoice = get_invoice(db, invoice_id)
    if not db_invoice:
        raise InvoiceNotFoundError(f"Invoice with id {invoice_id} not found.")

    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == data.po_id).first()
    if not po:
        raise PurchaseOrderNotFoundError(f"Purchase order with id {data.po_id} not found.")

    previous_po_id = db_invoice.po_id
    
    # We allow re-linking. If it's the same PO, we can just return early or proceed to re-verify. 
    # Let's proceed normally to ensure verification is up to date and audit is recorded.
    
    db_invoice.po_id = po.id

    # Create audit log
    audit = AuditLog(
        invoice_id=db_invoice.id,
        actor=data.actor,
        action="PO_LINKED",
        entity_name="INVOICE",
        entity_id=db_invoice.id,
        previous_state=f"PO: {previous_po_id}" if previous_po_id is not None else "PO: None",
        new_state=f"PO: {po.id}",
        comment=data.comment
    )
    db.add(audit)
    
    db.flush()

    # Re-verify the invoice
    verify_invoice(db, db_invoice.id)

    return db_invoice

class VendorNotFoundError(Exception):
    pass

def link_invoice_to_vendor(db: Session, invoice_id: int, data: InvoiceLinkVendor) -> Invoice:
    db_invoice = get_invoice(db, invoice_id)
    if not db_invoice:
        raise InvoiceNotFoundError(f"Invoice with id {invoice_id} not found.")

    from app.models.vendor import Vendor
    vendor = db.query(Vendor).filter(Vendor.id == data.vendor_id).first()
    if not vendor:
        raise VendorNotFoundError(f"Vendor with id {data.vendor_id} not found.")

    previous_vendor_id = db_invoice.vendor_id
    
    if previous_vendor_id == data.vendor_id:
        # Same vendor, no need to audit or reverify, return as is.
        # Or should we re-verify anyway? The instructions say: "Return safely/idempotently according to existing M3 PO-linking conventions."
        # Wait, M3 PO linking re-verifies and audits even for same-PO link. But the instruction for M4.1.4 says:
        # "If invoice.vendor_id already equals requested vendor_id: Do NOT create duplicate VENDOR_LINKED audit entries unnecessarily. Do NOT create unnecessary verification churn."
        return db_invoice

    db_invoice.vendor_id = vendor.id

    # Create audit log
    audit = AuditLog(
        invoice_id=db_invoice.id,
        actor=data.actor,
        action="VENDOR_LINKED",
        entity_name="INVOICE",
        entity_id=db_invoice.id,
        previous_state=f"Vendor: {previous_vendor_id}" if previous_vendor_id is not None else "Vendor: None",
        new_state=f"Vendor: {vendor.id}",
        comment=data.comment
    )
    db.add(audit)
    
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise InvoiceAlreadyExistsError("Invoice with this number already exists for the given vendor.")

    # Re-verify the invoice
    verify_invoice(db, db_invoice.id)

    return db_invoice

def map_invoice_item_to_po_item(db: Session, invoice_id: int, item_id: int, data: InvoiceItemMapPO) -> Invoice:
    db_invoice = get_invoice(db, invoice_id)
    if not db_invoice:
        raise InvoiceNotFoundError(f"Invoice with id {invoice_id} not found.")

    if not db_invoice.po_id:
        raise InvoiceNotLinkedToPOError("Invoice must have a linked Purchase Order.")

    db_item = db.query(InvoiceItem).filter(InvoiceItem.id == item_id, InvoiceItem.invoice_id == invoice_id).first()
    if not db_item:
        raise InvoiceItemNotFoundError(f"Invoice item with id {item_id} not found on this invoice.")

    target_po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == data.po_item_id).first()
    if not target_po_item:
        raise PurchaseOrderItemNotFoundError(f"PO item with id {data.po_item_id} not found.")

    if target_po_item.po_id != db_invoice.po_id:
        raise POItemBelongsToAnotherPOError("Target PO item does not belong to the invoice's linked PO.")

    previous_po_item_id = db_item.po_item_id

    if previous_po_item_id == data.po_item_id:
        return db_invoice

    db_item.po_item_id = data.po_item_id

    audit = AuditLog(
        invoice_id=db_invoice.id,
        actor=data.actor,
        action="PO_LINE_MAPPED",
        entity_name="INVOICE_ITEM",
        entity_id=db_item.id,
        previous_state=f"POItem: {previous_po_item_id}" if previous_po_item_id is not None else "POItem: None",
        new_state=f"POItem: {data.po_item_id}",
        comment=data.comment
    )
    db.add(audit)
    db.flush()

    verify_invoice(db, db_invoice.id)
    return db_invoice

def unmap_invoice_item_to_po_item(db: Session, invoice_id: int, item_id: int, data: InvoiceItemUnmapPO) -> Invoice:
    db_invoice = get_invoice(db, invoice_id)
    if not db_invoice:
        raise InvoiceNotFoundError(f"Invoice with id {invoice_id} not found.")

    db_item = db.query(InvoiceItem).filter(InvoiceItem.id == item_id, InvoiceItem.invoice_id == invoice_id).first()
    if not db_item:
        raise InvoiceItemNotFoundError(f"Invoice item with id {item_id} not found on this invoice.")

    previous_po_item_id = db_item.po_item_id

    if previous_po_item_id is None:
        return db_invoice

    db_item.po_item_id = None

    audit = AuditLog(
        invoice_id=db_invoice.id,
        actor=data.actor,
        action="PO_LINE_UNMAPPED",
        entity_name="INVOICE_ITEM",
        entity_id=db_item.id,
        previous_state=f"POItem: {previous_po_item_id}",
        new_state="POItem: None",
        comment=data.comment
    )
    db.add(audit)
    db.flush()

    verify_invoice(db, db_invoice.id)
    return db_invoice

