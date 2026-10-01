from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.vendor import VendorCreate, VendorUpdate, VendorRead
from app.services import vendor as vendor_service

router = APIRouter()

@router.post("/", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
def create_vendor(vendor_in: VendorCreate, db: Session = Depends(get_db)):
    try:
        vendor = vendor_service.create_vendor(db, vendor_in)
        db.commit()
        return vendor
    except vendor_service.VendorAlreadyExistsError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/", response_model=List[VendorRead])
def list_vendors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return vendor_service.list_vendors(db, skip=skip, limit=limit)

@router.get("/{vendor_id}", response_model=VendorRead)
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor = vendor_service.get_vendor(db, vendor_id)
    if not vendor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Vendor with id {vendor_id} not found.")
    return vendor

@router.patch("/{vendor_id}", response_model=VendorRead)
def update_vendor(vendor_id: int, vendor_in: VendorUpdate, db: Session = Depends(get_db)):
    try:
        vendor = vendor_service.update_vendor(db, vendor_id, vendor_in)
        db.commit()
        return vendor
    except vendor_service.VendorNotFoundError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except vendor_service.VendorAlreadyExistsError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
