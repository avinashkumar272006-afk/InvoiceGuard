import pytest
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta

from app.models.document_processing_job import DocumentProcessingJob, JobStatus
from app.models.invoice_document import InvoiceDocument, DocumentStatus
from app.models.invoice import Invoice
from app.models.vendor import Vendor
from app.database.connection import engine, SessionLocal

@pytest.fixture(scope="function")
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

def test_job_creation(db_session):
    doc = InvoiceDocument(
        filename="test.pdf",
        content_type="application/pdf",
        storage_path="raw/test.pdf",
        status=DocumentStatus.PENDING
    )
    db_session.add(doc)
    db_session.commit()
    
    job = DocumentProcessingJob(
        document_id=doc.id
    )
    db_session.add(job)
    db_session.commit()
    
    assert job.status == JobStatus.QUEUED
    assert job.attempt_count == 0
    assert job.next_attempt_at is not None
    assert job.started_at is None
    assert job.completed_at is None
    assert job.last_error is None

def test_document_relationship(db_session):
    doc = InvoiceDocument(
        filename="test2.pdf",
        content_type="application/pdf",
        storage_path="raw/test2.pdf",
    )
    db_session.add(doc)
    db_session.commit()
    
    job = DocumentProcessingJob(document_id=doc.id)
    db_session.add(job)
    db_session.commit()
    
    assert job.document.id == doc.id
    assert doc.processing_job.id == job.id

def test_unique_document_constraint(db_session):
    doc = InvoiceDocument(
        filename="test3.pdf",
        content_type="application/pdf",
        storage_path="raw/test3.pdf",
    )
    db_session.add(doc)
    db_session.commit()
    
    job1 = DocumentProcessingJob(document_id=doc.id)
    db_session.add(job1)
    db_session.commit()
    
    job2 = DocumentProcessingJob(document_id=doc.id)
    db_session.add(job2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_nullable_timestamps(db_session):
    doc = InvoiceDocument(
        filename="test4.pdf",
        content_type="application/pdf",
        storage_path="raw/test4.pdf",
    )
    db_session.add(doc)
    db_session.commit()
    
    job = DocumentProcessingJob(document_id=doc.id)
    db_session.add(job)
    db_session.commit()
    
    assert job.started_at is None
    assert job.completed_at is None

def test_retry_scheduling_field(db_session):
    doc = InvoiceDocument(
        filename="test5.pdf",
        content_type="application/pdf",
        storage_path="raw/test5.pdf",
    )
    db_session.add(doc)
    db_session.commit()
    
    job = DocumentProcessingJob(document_id=doc.id)
    db_session.add(job)
    db_session.commit()
    
    assert job.next_attempt_at is not None
    assert isinstance(job.next_attempt_at, datetime)

def test_error_field(db_session):
    doc = InvoiceDocument(
        filename="test6.pdf",
        content_type="application/pdf",
        storage_path="raw/test6.pdf",
    )
    db_session.add(doc)
    db_session.commit()
    
    job = DocumentProcessingJob(document_id=doc.id, last_error="Something went wrong")
    db_session.add(job)
    db_session.commit()
    
    assert job.last_error == "Something went wrong"

def test_existing_documents(db_session):
    # Documents can exist without a job
    doc = InvoiceDocument(
        filename="test7.pdf",
        content_type="application/pdf",
        storage_path="raw/test7.pdf",
    )
    db_session.add(doc)
    db_session.commit()
    
    assert doc.id is not None
    assert doc.processing_job is None

def test_existing_invoices(db_session):
    vendor = Vendor(
        name="Test Vendor"
    )
    db_session.add(vendor)
    db_session.commit()
    
    from datetime import date
    invoice = Invoice(
        invoice_number="INV-123",
        vendor_id=vendor.id,
        total_amount=100.00,
        issue_date=date.today()
    )
    db_session.add(invoice)
    db_session.commit()
    
    assert invoice.id is not None

def test_enum_values():
    assert JobStatus.QUEUED.value == "QUEUED"
    assert JobStatus.PROCESSING.value == "PROCESSING"
    assert JobStatus.COMPLETED.value == "COMPLETED"
    assert JobStatus.FAILED.value == "FAILED"
