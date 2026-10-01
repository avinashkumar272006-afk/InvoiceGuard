from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderUpdate

class PONotFoundError(Exception):
    pass

class POAlreadyExistsError(Exception):
    pass

def create_purchase_order(db: Session, po_in: PurchaseOrderCreate) -> PurchaseOrder:
    po_data = po_in.model_dump(exclude={"items"})
    db_po = PurchaseOrder(**po_data)
    
    for item_in in po_in.items:
        db_item = PurchaseOrderItem(**item_in.model_dump())
        db_po.items.append(db_item)
        
    db.add(db_po)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise POAlreadyExistsError(f"Purchase Order '{po_in.po_number}' already exists.")
    return db_po

def get_purchase_order(db: Session, po_id: int) -> Optional[PurchaseOrder]:
    return db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()

def list_purchase_orders(db: Session, skip: int = 0, limit: int = 100) -> List[PurchaseOrder]:
    return db.query(PurchaseOrder).offset(skip).limit(limit).all()

def update_purchase_order(db: Session, po_id: int, po_in: PurchaseOrderUpdate) -> PurchaseOrder:
    db_po = get_purchase_order(db, po_id)
    if not db_po:
        raise PONotFoundError(f"Purchase order with id {po_id} not found.")
    
    update_data = po_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_po, key, value)
        
    db.flush()
    return db_po
