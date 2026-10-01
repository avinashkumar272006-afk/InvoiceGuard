from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderRead
from app.services import purchase_order as po_service

router = APIRouter()

@router.post("/", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
def create_purchase_order(po_in: PurchaseOrderCreate, db: Session = Depends(get_db)):
    try:
        po = po_service.create_purchase_order(db, po_in)
        db.commit()
        return po
    except po_service.POAlreadyExistsError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/", response_model=List[PurchaseOrderRead])
def list_purchase_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return po_service.list_purchase_orders(db, skip=skip, limit=limit)

@router.get("/{po_id}", response_model=PurchaseOrderRead)
def get_purchase_order(po_id: int, db: Session = Depends(get_db)):
    po = po_service.get_purchase_order(db, po_id)
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase order with id {po_id} not found.")
    return po

@router.patch("/{po_id}", response_model=PurchaseOrderRead)
def update_purchase_order(po_id: int, po_in: PurchaseOrderUpdate, db: Session = Depends(get_db)):
    try:
        po = po_service.update_purchase_order(db, po_id, po_in)
        db.commit()
        return po
    except po_service.PONotFoundError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
