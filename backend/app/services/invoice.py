from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.invoice import Invoice, InvoiceItem
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate

class InvoiceNotFoundError(Exception):
    pass

class InvoiceAlreadyExistsError(Exception):
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
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()

def list_invoices(db: Session, skip: int = 0, limit: int = 100) -> List[Invoice]:
    return db.query(Invoice).offset(skip).limit(limit).all()

def update_invoice(db: Session, invoice_id: int, invoice_in: InvoiceUpdate) -> Invoice:
    db_invoice = get_invoice(db, invoice_id)
    if not db_invoice:
        raise InvoiceNotFoundError(f"Invoice with id {invoice_id} not found.")
    
    update_data = invoice_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_invoice, key, value)
        
    db.flush()
    return db_invoice
