import pytest
import io
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.models.invoice_document import DocumentStatus
from app.database.connection import engine, SessionLocal
from sqlalchemy.orm import Session

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

# Override the get_db dependency to use the isolated test session
# We apply it per-function so that we can easily rollback
@pytest.fixture(autouse=True)
def override_get_db(db_session):
    def _override_get_db():
        # Begin a nested transaction
        db_session.begin_nested()
        yield db_session
        if db_session.in_transaction():
            db_session.rollback()
            
    app.dependency_overrides[app.dependency_overrides.get("get_db") or __import__("app.database.connection", fromlist=["get_db"]).get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def mock_storage_service():
    with patch("app.api.v1.documents.storage_service") as mock_storage:
        yield mock_storage

def test_upload_valid_pdf(db_session: Session, mock_storage_service):
    # Dummy valid PDF signature
    file_content = b"%PDF-1.4\n%EOF"
    
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", file_content, "application/pdf")}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "id" in data
    assert data["filename"] == "test.pdf"
    assert data["status"] == "PENDING"
    assert "created_at" in data
    
    # Verify storage service was called
    mock_storage_service.upload_file.assert_called_once()
    call_args = mock_storage_service.upload_file.call_args[1]
    assert call_args["content_type"] == "application/pdf"
    assert call_args["storage_path"].startswith("raw/")
    assert call_args["storage_path"].endswith(".pdf")

def test_upload_valid_png(db_session, mock_storage_service):
    file_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("image.png", file_content, "image/png")}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    mock_storage_service.upload_file.assert_called_once()
    assert mock_storage_service.upload_file.call_args[1]["storage_path"].endswith(".png")

def test_upload_valid_jpeg(db_session, mock_storage_service):
    file_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
    
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("image.jpg", file_content, "image/jpeg")}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    mock_storage_service.upload_file.assert_called_once()
    assert mock_storage_service.upload_file.call_args[1]["storage_path"].endswith(".jpg")

def test_upload_unsupported_mime(db_session, mock_storage_service):
    file_content = b"just some text"
    
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", file_content, "text/plain")}
    )
    
    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    mock_storage_service.upload_file.assert_not_called()

def test_upload_invalid_signature_pdf(db_session, mock_storage_service):
    # A text file pretending to be a PDF
    file_content = b"just some text pretending to be pdf"
    
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", file_content, "application/pdf")}
    )
    
    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    mock_storage_service.upload_file.assert_not_called()

def test_upload_oversized_file(db_session, mock_storage_service):
    # Using a mocked UploadFile read to simulate a large file since 10MB bytes takes a lot of memory
    # Actually we can just override MAX_FILE_SIZE for the test
    with patch("app.services.validation.MAX_FILE_SIZE", 50):
        # Provide a file larger than 50 bytes with valid PDF signature
        file_content = b"%PDF-1.4\n" + (b"0" * 100)
        
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("large.pdf", file_content, "application/pdf")}
        )
        
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        mock_storage_service.upload_file.assert_not_called()

def test_upload_storage_failure(db_session, mock_storage_service):
    # Simulate a failure in storage upload
    mock_storage_service.upload_file.side_effect = Exception("Storage error")
    
    file_content = b"%PDF-1.4\n%EOF"
    
    from app.models.invoice_document import InvoiceDocument
    docs_before = len(db_session.query(InvoiceDocument).all())
    
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", file_content, "application/pdf")}
    )
    
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    # Verify the document was not inserted into the database
    docs_after = len(db_session.query(InvoiceDocument).all())
    assert docs_after == docs_before

def test_upload_db_failure_cleans_up_storage(db_session, mock_storage_service):
    file_content = b"%PDF-1.4\n%EOF"
    
    # Mock db.commit to raise an exception
    with patch("sqlalchemy.orm.Session.commit", side_effect=Exception("DB Error")):
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", file_content, "application/pdf")}
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        
        # Verify storage upload was called
        mock_storage_service.upload_file.assert_called_once()
        
        mock_storage_service.delete_file.assert_called_once()
        call_args = mock_storage_service.delete_file.call_args[0]
        assert call_args[0].startswith("raw/")

def test_process_document_success(db_session):
    import uuid
    doc_id = uuid.uuid4()
    
    with patch("app.api.v1.documents.process_document") as mock_process:
        from app.services.document_processing import DocumentProcessingResult
        mock_process.return_value = DocumentProcessingResult(success=True, message="Document successfully processed.", invoice_id=1)
        
        response = client.post(f"/api/v1/documents/{doc_id}/process")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["invoice_id"] == 1
        assert data["message"] == "Document successfully processed."

def test_process_document_not_found(db_session):
    import uuid
    doc_id = uuid.uuid4()
    
    with patch("app.api.v1.documents.process_document") as mock_process:
        from app.services.document_processing import DocumentProcessingResult
        mock_process.return_value = DocumentProcessingResult(success=False, message="Document not found.")
        
        response = client.post(f"/api/v1/documents/{doc_id}/process")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

def test_process_document_already_extracted(db_session):
    import uuid
    doc_id = uuid.uuid4()
    
    with patch("app.api.v1.documents.process_document") as mock_process:
        from app.services.document_processing import DocumentProcessingResult
        mock_process.return_value = DocumentProcessingResult(success=True, message="Document already extracted.", invoice_id=1)
        
        response = client.post(f"/api/v1/documents/{doc_id}/process")
        
        assert response.status_code == status.HTTP_409_CONFLICT

def test_process_document_currently_extracting(db_session):
    import uuid
    doc_id = uuid.uuid4()
    
    with patch("app.api.v1.documents.process_document") as mock_process:
        from app.services.document_processing import DocumentProcessingResult
        mock_process.return_value = DocumentProcessingResult(success=False, message="Document is currently being processed.")
        
        response = client.post(f"/api/v1/documents/{doc_id}/process")
        
        assert response.status_code == status.HTTP_409_CONFLICT

def test_process_document_validation_failure(db_session):
    import uuid
    doc_id = uuid.uuid4()
    
    with patch("app.api.v1.documents.process_document") as mock_process:
        from app.services.document_processing import DocumentProcessingResult
        mock_process.return_value = DocumentProcessingResult(success=False, message="Business validation failed: ERR: math error")
        
        response = client.post(f"/api/v1/documents/{doc_id}/process")
        
        # We expect 200 OK with success=False, as defined by orchestration logic for normal failures
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is False
        assert "validation failed" in data["message"]
