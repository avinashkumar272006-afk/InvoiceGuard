import logging
import json
import pytest
from fastapi.testclient import TestClient
from typing import Generator
import uuid

from app.main import app
from app.core.logging import StructuredJSONFormatter, request_id_var
from app.core.config import settings

@pytest.fixture
def client() -> Generator:
    with TestClient(app) as c:
        yield c

def test_formatter_redacts_sensitive_keys():
    formatter = StructuredJSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Test message",
        args=(),
        exc_info=None
    )
    # Add sensitive kwargs
    record.__dict__["gemini_api_key"] = "secret-gemini-key"
    record.__dict__["supabase_service_key"] = "secret-supabase-key"
    record.__dict__["document_content"] = "secret-document-content"
    record.__dict__["safe_key"] = "safe-value"
    
    formatted_str = formatter.format(record)
    parsed = json.loads(formatted_str)
    
    assert parsed["safe_key"] == "safe-value"
    assert parsed["gemini_api_key"] == "[REDACTED]"
    assert parsed["supabase_service_key"] == "[REDACTED]"
    assert parsed["document_content"] == "[REDACTED]"
    assert "secret-gemini-key" not in formatted_str
    assert "secret-supabase-key" not in formatted_str
    assert "secret-document-content" not in formatted_str

def test_formatter_redacts_sensitive_values():
    formatter = StructuredJSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Test message",
        args=(),
        exc_info=None
    )
    # Mock settings values for redaction test
    old_supabase_key = settings.supabase_service_key
    settings.supabase_service_key = "real-secret-key-12345"
    
    try:
        record.__dict__["some_url"] = f"https://example.com?token={settings.supabase_service_key}"
        
        formatted_str = formatter.format(record)
        parsed = json.loads(formatted_str)
        
        assert parsed["some_url"] == "[REDACTED_VALUE]"
        assert "real-secret-key-12345" not in formatted_str
    finally:
        settings.supabase_service_key = old_supabase_key

def test_request_id_middleware_generates_id(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"]

def test_request_id_middleware_propagates_id(client):
    test_id = str(uuid.uuid4())
    response = client.get("/health", headers={"X-Request-ID": test_id})
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"] == test_id

def test_unexpected_errors_logged_safely(caplog):
    # Add a temporary route to force an error
    @app.get("/test-error-for-logging")
    async def trigger_error():
        raise ValueError("Secret failure that should not leak")
    
    # We must set raise_server_exceptions=False to test exception handlers properly
    # Otherwise TestClient re-raises the unhandled exception.
    test_client = TestClient(app, raise_server_exceptions=False)
    
    with caplog.at_level(logging.ERROR):
        response = test_client.get("/test-error-for-logging")
        
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "Secret failure that should not leak" not in response.text
    
    # But it is in the logs
    assert "Secret failure that should not leak" in caplog.text
    
def test_document_processing_safe_identifiers(caplog):
    from app.services.document_processing import _fail_document
    from unittest.mock import MagicMock
    
    db = MagicMock()
    doc_id = uuid.uuid4()
    
    with caplog.at_level(logging.INFO):
        _fail_document(db, doc_id, "Test error message", "extraction_error")
        
    log_record = next(r for r in caplog.records if r.msg == "document_processing_failed")
    assert log_record.document_id == str(doc_id)
    assert log_record.error_category == "extraction_error"
    # Ensure no full document content or keys were logged
    assert not hasattr(log_record, "document_content")
    assert not hasattr(log_record, "pdf_bytes")
