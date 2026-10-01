from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate, VendorUpdate

class VendorNotFoundError(Exception):
    pass

class VendorAlreadyExistsError(Exception):
    pass

def create_vendor(db: Session, vendor_in: VendorCreate) -> Vendor:
    db_vendor = Vendor(**vendor_in.model_dump())
    db.add(db_vendor)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise VendorAlreadyExistsError("Vendor with this tax_id already exists.")
    return db_vendor

def get_vendor(db: Session, vendor_id: int) -> Optional[Vendor]:
    return db.query(Vendor).filter(Vendor.id == vendor_id).first()

def list_vendors(db: Session, skip: int = 0, limit: int = 100) -> List[Vendor]:
    return db.query(Vendor).offset(skip).limit(limit).all()

def update_vendor(db: Session, vendor_id: int, vendor_in: VendorUpdate) -> Vendor:
    db_vendor = get_vendor(db, vendor_id)
    if not db_vendor:
        raise VendorNotFoundError(f"Vendor with id {vendor_id} not found.")
    
    update_data = vendor_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_vendor, key, value)
    
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise VendorAlreadyExistsError("Update failed: Vendor with this tax_id already exists.")
    return db_vendor
