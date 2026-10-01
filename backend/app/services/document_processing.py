import time
import logging
from typing import Optional, Any
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.invoice_document import InvoiceDocument, DocumentStatus
from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate
from app.services.storage import storage_service
from app.services.extraction.gemini import (
    GeminiInvoiceExtractor, 
    ExtractorProviderError
)
from app.services.business_validation import BusinessValidationService
from app.services.invoice import create_invoice
from app.services.verification import verify_invoice

logger = logging.getLogger(__name__)

class DocumentProcessingResult:
    def __init__(self, success: bool, message: str, invoice_id: Optional[int] = None):
        self.success = success
        self.message = message
        self.invoice_id = invoice_id

def _fail_document(db: Session, document_id: Any, error_message: str, error_category: str = "unexpected_error") -> DocumentProcessingResult:
    try:
        doc = db.query(InvoiceDocument).filter(InvoiceDocument.id == document_id).first()
        if doc:
            doc.status = DocumentStatus.FAILED
            doc.error_message = error_message[:1000]
            db.commit()
            logger.info("document_processing_failed", extra={
                "document_id": str(document_id),
                "error_category": error_category
            })
    except Exception:
        logger.exception("Failed to update document status to FAILED", extra={"document_id": str(document_id)})
        db.rollback()
    return DocumentProcessingResult(success=False, message=error_message)

def process_document(db: Session, document_id: Any) -> DocumentProcessingResult:
    start_time = time.time()
    logger.info("document_processing_started", extra={"document_id": str(document_id)})
    
    # Phase A: Lock and validate state
    doc = db.query(InvoiceDocument).filter(InvoiceDocument.id == document_id).with_for_update().first()
    if not doc:
        logger.warning("document_not_found", extra={"document_id": str(document_id)})
        return DocumentProcessingResult(success=False, message="Document not found.")

    if doc.status == DocumentStatus.EXTRACTED:
        db.rollback()
        logger.info("document_already_extracted", extra={"document_id": str(document_id), "invoice_id": doc.invoice_id})
        return DocumentProcessingResult(success=True, message="Document already extracted.", invoice_id=doc.invoice_id)
        
    if doc.status == DocumentStatus.EXTRACTING:
        db.rollback()
        logger.warning("document_concurrent_processing", extra={"document_id": str(document_id)})
        return DocumentProcessingResult(success=False, message="Document is currently being processed.")

    doc.status = DocumentStatus.EXTRACTING
    doc.error_message = None
    
    storage_path = doc.storage_path
    content_type = doc.content_type
    
    db.commit()

    # Phase B: Network boundary (No active DB transaction)
    try:
        logger.info("document_storage_retrieving", extra={"document_id": str(document_id)})
        file_bytes = storage_service.download_file(storage_path)
        logger.info("document_storage_retrieved", extra={"document_id": str(document_id)})
        
        extractor = GeminiInvoiceExtractor()
        extracted_data = None
        last_err = None
        
        logger.info("document_extraction_started", extra={"document_id": str(document_id)})
        extract_start = time.time()
        for attempt in range(3):
            try:
                extracted_data = extractor.extract_invoice(file_bytes, content_type)
                break
            except ExtractorProviderError as e:
                last_err = e
                logger.warning("Provider error during extraction", extra={"document_id": str(document_id), "attempt": attempt+1})
            except Exception as e:
                raise e
        else:
            if last_err:
                raise last_err
                
        extract_duration = round((time.time() - extract_start) * 1000, 2)
        logger.info("document_extraction_completed", extra={"document_id": str(document_id), "duration_ms": extract_duration})

    except Exception as e:
        safe_msg = f"Extraction failed: {type(e).__name__}"
        logger.exception("Extraction failed", extra={"document_id": str(document_id)})
        return _fail_document(db, document_id, safe_msg, error_category="extraction_error")

    # Phase C: Business Validation
    try:
        logger.info("business_validation_started", extra={"document_id": str(document_id)})
        validation_result = BusinessValidationService.validate(db, extracted_data)
    except Exception:
        logger.exception("Validation engine error", extra={"document_id": str(document_id)})
        return _fail_document(db, document_id, "Validation engine error.", error_category="validation_error")

    if not validation_result.is_valid:
        issues_text = "; ".join([f"{issue.code}: {issue.message}" for issue in validation_result.issues])
        logger.info("business_validation_failed", extra={"document_id": str(document_id)})
        return _fail_document(db, document_id, f"Business validation failed: {issues_text}", error_category="validation_error")

    # Phase D: Invoice persistence
    try:
        items = []
        if extracted_data.items:
            for item in extracted_data.items:
                items.append(
                    InvoiceItemCreate(
                        description=item.description,
                        quantity=Decimal(item.quantity),
                        unit_price=Decimal(item.unit_price),
                        total_price=Decimal(item.total_price),
                    )
                )

        invoice_in = InvoiceCreate(
            invoice_number=extracted_data.invoice_number,
            vendor_id=validation_result.vendor_id,
            po_id=None,
            issue_date=validation_result.parsed_issue_date,
            total_amount=validation_result.parsed_total_amount,
            items=items
        )

        doc_update = db.query(InvoiceDocument).filter(InvoiceDocument.id == document_id).with_for_update().first()
        if not doc_update or doc_update.status != DocumentStatus.EXTRACTING:
            db.rollback()
            logger.error("State conflict during persistence", extra={"document_id": str(document_id)})
            return DocumentProcessingResult(success=False, message="State conflict during persistence.")

        invoice = create_invoice(db, invoice_in)
        
        doc_update.invoice_id = invoice.id
        doc_update.status = DocumentStatus.EXTRACTED
        
        db.commit()
        logger.info("invoice_created", extra={"document_id": str(document_id), "invoice_id": invoice.id})
        
    except IntegrityError:
        db.rollback()
        logger.exception("Integrity error during persistence", extra={"document_id": str(document_id)})
        return _fail_document(db, document_id, "Failed to persist invoice due to duplicate or invalid data constraint.", error_category="database_error")
    except Exception:
        db.rollback()
        logger.exception("Persistence error", extra={"document_id": str(document_id)})
        return _fail_document(db, document_id, "Failed to persist invoice.", error_category="database_error")

    # Phase E: Invoke verification
    try:
        verify_invoice(db, invoice.id)
    except Exception:
        logger.exception("Verification failed", extra={"document_id": str(document_id), "invoice_id": invoice.id})
        # Document is technically EXTRACTED even if verification fails.
        
    processing_duration = round((time.time() - start_time) * 1000, 2)
    logger.info("document_processing_completed", extra={
        "document_id": str(document_id), 
        "invoice_id": invoice.id,
        "duration_ms": processing_duration
    })
    return DocumentProcessingResult(success=True, message="Document successfully processed.", invoice_id=invoice.id)
