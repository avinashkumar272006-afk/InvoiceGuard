import uuid
import logging
from typing import Any

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.invoice_document import InvoiceDocument, DocumentStatus
from app.schemas.document import DocumentResponse, DocumentProcessingResponse, DocumentUrlResponse
from app.services.validation import validate_file
from app.services.storage import storage_service
from app.services.document_processing import process_document

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> Any:
    """
    Uploads a new invoice document to storage and creates a tracking record in the database.
    """
    # 1. Validate file (size, MIME, magic bytes)
    extension = await validate_file(file)
    
    # 2. Generate storage path
    document_id = uuid.uuid4()
    storage_path = f"raw/{document_id}{extension}"
    
    # Read file content into memory for upload
    await file.seek(0)
    file_content = await file.read()
    
    # 3. Upload to Supabase Storage
    try:
        storage_service.upload_file(
            file_content=file_content,
            storage_path=storage_path,
            content_type=file.content_type
        )
    except Exception:
        logger.exception("Storage upload failed", extra={"upload_filename": file.filename})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store document"
        )
        
    # 4. Save to Database
    try:
        db_doc = InvoiceDocument(
            id=document_id,
            filename=file.filename,
            content_type=file.content_type,
            storage_path=storage_path,
            status=DocumentStatus.PENDING
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        return db_doc
        
    except Exception:
        logger.exception("Database insert failed for document", extra={"document_id": str(document_id)})
        db.rollback()
        
        # Cleanup orphaned storage file
        try:
            storage_service.delete_file(storage_path)
        except Exception:
            logger.exception("Failed to cleanup orphaned storage file", extra={"storage_path": storage_path})
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track document in database"
        )

@router.post("/{document_id}/process", response_model=DocumentProcessingResponse, status_code=status.HTTP_200_OK)
def process_invoice_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db)
) -> Any:
    """
    Processes an uploaded invoice document by extracting structured data 
    and running business validation.
    """
    result = process_document(db, document_id)
    
    if not result.success:
        if result.message == "Document not found.":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.message)
        if result.message == "Document is currently being processed.":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.message)
            
    if result.success and result.message == "Document already extracted.":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.message)
        
    return result

@router.get("/{document_id}/file", response_model=DocumentUrlResponse, status_code=status.HTTP_200_OK)
def get_document_file(
    document_id: uuid.UUID,
    db: Session = Depends(get_db)
) -> Any:
    """
    Returns a short-lived signed URL to securely view the document.
    """
    doc = db.query(InvoiceDocument).filter(InvoiceDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        
    try:
        expires_in = 60
        url = storage_service.create_signed_url(doc.storage_path, expires_in=expires_in)
        return DocumentUrlResponse(url=url, expires_in=expires_in)
    except Exception:
        # Do not expose internal Supabase errors
        logger.exception("Failed to generate signed URL", extra={"document_id": str(document_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve document file")
