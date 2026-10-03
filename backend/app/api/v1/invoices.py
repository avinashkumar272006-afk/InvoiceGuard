from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate, InvoiceRead, InvoiceLinkPO
from app.services import invoice as invoice_service

router = APIRouter()

@router.post("/", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(invoice_in: InvoiceCreate, db: Session = Depends(get_db)):
    try:
        invoice = invoice_service.create_invoice(db, invoice_in)
        db.commit()
        return invoice
    except invoice_service.InvoiceAlreadyExistsError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/", response_model=List[InvoiceRead])
def list_invoices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return invoice_service.list_invoices(db, skip=skip, limit=limit)

@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = invoice_service.get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice with id {invoice_id} not found.")
    return invoice

@router.patch("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(invoice_id: int, invoice_in: InvoiceUpdate, db: Session = Depends(get_db)):
    try:
        invoice = invoice_service.update_invoice(db, invoice_id, invoice_in)
        db.commit()
        return invoice
    except invoice_service.InvoiceNotFoundError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.post("/{invoice_id}/link-po", response_model=InvoiceRead)
def link_invoice_to_purchase_order(invoice_id: int, data: InvoiceLinkPO, db: Session = Depends(get_db)):
    try:
        invoice = invoice_service.link_invoice_to_purchase_order(db, invoice_id, data)
        db.commit()
        return invoice
    except invoice_service.InvoiceNotFoundError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except invoice_service.PurchaseOrderNotFoundError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

from app.schemas.verification import VerificationRead
from app.services import verification as verification_service

@router.post("/{invoice_id}/verify", response_model=VerificationRead)
def verify_invoice(invoice_id: int, db: Session = Depends(get_db)):
    try:
        verification = verification_service.verify_invoice(db, invoice_id)
        return verification
    except verification_service.InvoiceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get("/{invoice_id}/verification", response_model=VerificationRead)
def get_verification(invoice_id: int, db: Session = Depends(get_db)):
    try:
        verification = verification_service.get_verification(db, invoice_id)
        if not verification:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No verification found for invoice {invoice_id}.")
        return verification
    except verification_service.InvoiceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

from app.schemas.audit import ReviewCreate, ExceptionResolveCreate, AuditLogRead
from app.services import review as review_service

@router.post("/{invoice_id}/exceptions/{exception_id}/resolve", response_model=dict)
def resolve_exception(invoice_id: int, exception_id: int, data: ExceptionResolveCreate, db: Session = Depends(get_db)):
    try:
        exc = review_service.resolve_exception(db, invoice_id, exception_id, data)
        return {"id": exc.id, "resolved": exc.resolved}
    except review_service.InvoiceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except review_service.ExceptionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except review_service.InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{invoice_id}/review", response_model=InvoiceRead)
def review_invoice(invoice_id: int, data: ReviewCreate, db: Session = Depends(get_db)):
    try:
        invoice = review_service.review_invoice(db, invoice_id, data)
        return invoice
    except review_service.InvoiceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except review_service.InvalidStateTransitionError as e:
        if "unresolved exceptions" in str(e):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{invoice_id}/audit-logs", response_model=list[AuditLogRead])
def get_audit_logs(invoice_id: int, db: Session = Depends(get_db)):
    try:
        logs = review_service.get_audit_logs(db, invoice_id)
        return logs
    except review_service.InvoiceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
