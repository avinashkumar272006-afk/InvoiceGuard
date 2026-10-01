import pytest
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError
from app.models.invoice_document import InvoiceDocument, DocumentStatus
from app.models.invoice import Invoice
from app.services.document_processing import process_document, DocumentProcessingResult
from app.services.extraction.gemini import ExtractorProviderError, ExtractorValidationError
from app.schemas.extraction import ExtractedInvoiceSchema, ExtractedInvoiceItem, ExtractionMetadata
from app.schemas.business_validation import BusinessValidationResult, BusinessValidationIssue

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_storage():
    with patch("app.services.document_processing.storage_service") as mock:
        yield mock

@pytest.fixture
def mock_extractor():
    with patch("app.services.document_processing.GeminiInvoiceExtractor") as MockExtractor:
        extractor_instance = MagicMock()
        MockExtractor.return_value = extractor_instance
        yield extractor_instance

@pytest.fixture
def mock_validation():
    with patch("app.services.document_processing.BusinessValidationService") as mock:
        yield mock

@pytest.fixture
def mock_create_invoice():
    with patch("app.services.document_processing.create_invoice") as mock:
        yield mock

@pytest.fixture
def mock_verify_invoice():
    with patch("app.services.document_processing.verify_invoice") as mock:
        yield mock

def get_base_document(status=DocumentStatus.PENDING):
    doc = InvoiceDocument(
        id=uuid.uuid4(),
        filename="test.pdf",
        content_type="application/pdf",
        storage_path="raw/test.pdf",
        status=status
    )
    return doc

def test_process_valid_document(mock_db, mock_storage, mock_extractor, mock_validation, mock_create_invoice, mock_verify_invoice):
    doc = get_base_document()
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = doc
    
    mock_storage.download_file.return_value = b"test_bytes"
    
    extracted = ExtractedInvoiceSchema(
        invoice_number="INV-001",
        issue_date_raw="2026-09-29",
        vendor_name_raw="Test Vendor",
        total_amount="100.00",
        items=[ExtractedInvoiceItem(description="Item", quantity="1", unit_price="100", total_price="100")],
        metadata=ExtractionMetadata()
    )
    mock_extractor.extract_invoice.return_value = extracted
    
    validation_res = BusinessValidationResult(
        is_valid=True,
        vendor_id=1,
        parsed_issue_date=date(2026, 9, 29),
        parsed_total_amount=Decimal("100.00"),
        issues=[],
        warnings=[]
    )
    mock_validation.validate.return_value = validation_res
    
    invoice = Invoice(id=99)
    mock_create_invoice.return_value = invoice
    
    result = process_document(mock_db, doc.id)
    
    assert result.success is True
    assert result.invoice_id == 99
    
    assert doc.status == DocumentStatus.EXTRACTED
    assert doc.invoice_id == 99
    
    mock_storage.download_file.assert_called_once_with("raw/test.pdf")
    mock_extractor.extract_invoice.assert_called_once_with(b"test_bytes", "application/pdf")
    mock_validation.validate.assert_called_once()
    mock_create_invoice.assert_called_once()
    
    invoice_in = mock_create_invoice.call_args[0][1]
    assert invoice_in.invoice_number == "INV-001"
    assert len(invoice_in.items) == 1

def test_already_extracted(mock_db):
    doc = get_base_document(DocumentStatus.EXTRACTED)
    doc.invoice_id = 99
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = doc
    
    result = process_document(mock_db, doc.id)
    assert result.success is True
    assert result.message == "Document already extracted."
    assert result.invoice_id == 99
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()

def test_currently_extracting(mock_db):
    doc = get_base_document(DocumentStatus.EXTRACTING)
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = doc
    
    result = process_document(mock_db, doc.id)
    assert result.success is False
    assert result.message == "Document is currently being processed."

def test_storage_failure(mock_db, mock_storage):
    doc = get_base_document()
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = doc
    mock_db.query.return_value.filter.return_value.first.return_value = doc
    
    mock_storage.download_file.side_effect = Exception("S3 down")
    
    result = process_document(mock_db, doc.id)
    assert result.success is False
    assert doc.status == DocumentStatus.FAILED
    assert "Extraction failed" in doc.error_message
    assert "S3 down" not in doc.error_message # Type is included, not message to avoid leaking secrets

def test_gemini_retry_and_fail(mock_db, mock_storage, mock_extractor):
    doc = get_base_document()
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = doc
    mock_db.query.return_value.filter.return_value.first.return_value = doc
    
    mock_storage.download_file.return_value = b"bytes"
    mock_extractor.extract_invoice.side_effect = ExtractorProviderError("429 Too Many Requests")
    
    result = process_document(mock_db, doc.id)
    assert result.success is False
    assert doc.status == DocumentStatus.FAILED
    assert mock_extractor.extract_invoice.call_count == 3 # Retry limit

def test_non_retryable_extraction_fail(mock_db, mock_storage, mock_extractor):
    doc = get_base_document()
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = doc
    mock_db.query.return_value.filter.return_value.first.return_value = doc
    
    mock_storage.download_file.return_value = b"bytes"
    mock_extractor.extract_invoice.side_effect = ExtractorValidationError("Schema mismatch")
    
    result = process_document(mock_db, doc.id)
    assert result.success is False
    assert doc.status == DocumentStatus.FAILED
    assert mock_extractor.extract_invoice.call_count == 1 # No retry

def test_business_validation_failure(mock_db, mock_storage, mock_extractor, mock_validation, mock_create_invoice):
    doc = get_base_document()
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = doc
    mock_db.query.return_value.filter.return_value.first.return_value = doc
    
    mock_extractor.extract_invoice.return_value = ExtractedInvoiceSchema(
        invoice_number="INV", issue_date_raw="2026-01-01", vendor_name_raw="V", total_amount="1", items=[], metadata=ExtractionMetadata()
    )
    
    validation_res = BusinessValidationResult(
        is_valid=False,
        issues=[BusinessValidationIssue(code="ERR", message="Bad math")],
        warnings=[]
    )
    mock_validation.validate.return_value = validation_res
    
    result = process_document(mock_db, doc.id)
    
    assert result.success is False
    assert "Business validation failed" in result.message
    assert doc.status == DocumentStatus.FAILED
    mock_create_invoice.assert_not_called()

def test_database_persistence_failure(mock_db, mock_storage, mock_extractor, mock_validation, mock_create_invoice):
    doc = get_base_document()
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = doc
    mock_db.query.return_value.filter.return_value.first.return_value = doc
    
    mock_extractor.extract_invoice.return_value = ExtractedInvoiceSchema(
        invoice_number="INV", issue_date_raw="2026-01-01", vendor_name_raw="V", total_amount="1", items=[], metadata=ExtractionMetadata()
    )
    
    mock_validation.validate.return_value = BusinessValidationResult(
        is_valid=True, vendor_id=1, parsed_issue_date=date(2026, 1, 1), parsed_total_amount=Decimal("1"), issues=[], warnings=[]
    )
    
    mock_create_invoice.side_effect = IntegrityError("duplicate", params={}, orig=Exception())
    
    result = process_document(mock_db, doc.id)
    
    assert result.success is False
    assert "constraint" in result.message
    assert doc.status == DocumentStatus.FAILED
    assert mock_db.rollback.call_count >= 1

def test_no_secrets_in_error_message(mock_db, mock_storage):
    doc = get_base_document()
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = doc
    mock_db.query.return_value.filter.return_value.first.return_value = doc
    
    # Simulating an error that contains a secret
    mock_storage.download_file.side_effect = Exception("Database url is postgresql://user:secret@localhost/db")
    
    process_document(mock_db, doc.id)
    
    assert doc.status == DocumentStatus.FAILED
    # Ensure error type is logged, but not the explicit message which might have secrets
    assert "postgresql://user:secret" not in doc.error_message
    assert "Exception" in doc.error_message
