import pytest
import uuid
import threading
from datetime import datetime, timedelta
from app.models.document_processing_job import DocumentProcessingJob, JobStatus
from app.models.invoice_document import InvoiceDocument
from app.services.worker import acquire_next_job, fail_job, recover_stale_job
from app.core.config import settings
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.connection import SessionLocal

@pytest.fixture(scope="function")
def db_session():
    session = SessionLocal()
    session.query(DocumentProcessingJob).delete()
    session.query(InvoiceDocument).delete()
    session.commit()
    yield session
    session.query(DocumentProcessingJob).delete()
    session.query(InvoiceDocument).delete()
    session.commit()
    session.close()

from unittest.mock import patch

@pytest.fixture
def SessionLocal_fixture():
    return SessionLocal

@pytest.fixture
def test_document(db_session: Session):
    doc = InvoiceDocument(
        filename=f"test_retry_{uuid.uuid4()}.pdf",
        content_type="application/pdf",
        storage_path=f"test/path_{uuid.uuid4()}.pdf"
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc

@pytest.fixture
def queued_job(db_session: Session, test_document: InvoiceDocument):
    job = DocumentProcessingJob(
        document_id=test_document.id,
        status=JobStatus.QUEUED,
        attempt_count=0,
        next_attempt_at=datetime.utcnow() - timedelta(seconds=1)
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job

# --- Retry tests ---

def test_first_attempt_increments_attempt_count(db_session: Session, queued_job: DocumentProcessingJob):
    job = acquire_next_job(db_session)
    assert job is not None
    assert job.id == queued_job.id
    assert job.attempt_count == 1
    assert job.status == JobStatus.PROCESSING
    assert job.started_at is not None

def test_retryable_failure_schedules_queued(db_session: Session, queued_job: DocumentProcessingJob):
    job = acquire_next_job(db_session)
    fail_job(db_session, str(job.id), "Temporary failure")
    
    db_session.expire_all()
    job_after = db_session.query(DocumentProcessingJob).get(job.id)
    assert job_after.status == JobStatus.QUEUED
    assert job_after.last_error == "Temporary failure"
    assert job_after.started_at is None
    assert job_after.attempt_count == 1 # Did not increment again

def test_first_retry_uses_base_delay(db_session: Session, queued_job: DocumentProcessingJob):
    job = acquire_next_job(db_session)
    now = datetime.utcnow()
    fail_job(db_session, str(job.id), "Failed")
    
    db_session.expire_all()
    job_after = db_session.query(DocumentProcessingJob).get(job.id)
    
    expected_delay = settings.worker_retry_base_delay_seconds * (2 ** (job_after.attempt_count - 1))
    assert expected_delay == 5
    
    diff = (job_after.next_attempt_at - job_after.updated_at).total_seconds()
    assert 4 < diff < 6

def test_second_retry_uses_exponential_delay(db_session: Session, queued_job: DocumentProcessingJob):
    # Attempt 1
    job = acquire_next_job(db_session)
    fail_job(db_session, str(job.id), "Failed 1")
    
    # Fast-forward next_attempt_at to allow Attempt 2
    job_after1 = db_session.query(DocumentProcessingJob).get(job.id)
    job_after1.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()
    
    # Attempt 2
    job = acquire_next_job(db_session)
    assert job.attempt_count == 2
    
    now = datetime.utcnow()
    fail_job(db_session, str(job.id), "Failed 2")
    
    db_session.expire_all()
    job_after2 = db_session.query(DocumentProcessingJob).get(job.id)
    
    expected_delay = settings.worker_retry_base_delay_seconds * (2 ** (job_after2.attempt_count - 1))
    assert expected_delay == 10
    
    diff = (job_after2.next_attempt_at - job_after2.updated_at).total_seconds()
    assert 9 < diff < 11

def test_third_retry_uses_exponential_delay(db_session: Session, queued_job: DocumentProcessingJob):
    # Skip attempt 1 and 2 logic and directly set attempt_count=2
    queued_job.attempt_count = 2
    db_session.commit()
    
    job = acquire_next_job(db_session)
    assert job.attempt_count == 3
    
    now = datetime.utcnow()
    fail_job(db_session, str(job.id), "Failed 3")
    
    db_session.expire_all()
    job_after = db_session.query(DocumentProcessingJob).get(job.id)
    
    # Attempt count is now 3. Base * 2^2 = 5 * 4 = 20
    # Wait, max attempts is 3 by default! If max attempts is 3, failing with attempt_count 3 should mark it FAILED.
    assert job_after.status == JobStatus.FAILED
    assert job_after.completed_at is not None

def test_delay_capped_at_max(db_session: Session, queued_job: DocumentProcessingJob):
    with patch("app.core.config.settings.worker_max_attempts", 10):
        queued_job.attempt_count = 6
        db_session.commit()
        
        job = acquire_next_job(db_session)
        assert job.attempt_count == 7
        
        now = datetime.utcnow()
        fail_job(db_session, str(job.id), "Failed")
        
        db_session.expire_all()
        job_after = db_session.query(DocumentProcessingJob).get(job.id)
        
        # 5 * 2^6 = 5 * 64 = 320 -> should cap at 300
        assert job_after.status == JobStatus.QUEUED
        diff = (job_after.next_attempt_at - job_after.updated_at).total_seconds()
        assert 295 < diff < 305

def test_max_attempts_transition_to_failed(db_session: Session, queued_job: DocumentProcessingJob):
    queued_job.attempt_count = settings.worker_max_attempts - 1
    db_session.commit()
    
    job = acquire_next_job(db_session)
    assert job.attempt_count == settings.worker_max_attempts
    
    fail_job(db_session, str(job.id), "Max fail")
    
    db_session.expire_all()
    job_after = db_session.query(DocumentProcessingJob).get(job.id)
    
    assert job_after.status == JobStatus.FAILED
    assert job_after.last_error == "Max fail"
    assert job_after.completed_at is not None

def test_failed_job_not_scheduled(db_session: Session, queued_job: DocumentProcessingJob):
    queued_job.status = JobStatus.FAILED
    db_session.commit()
    
    job = acquire_next_job(db_session)
    assert job is None

def test_future_next_attempt_prevents_acquisition(db_session: Session, queued_job: DocumentProcessingJob):
    queued_job.next_attempt_at = datetime.utcnow() + timedelta(minutes=10)
    db_session.commit()
    
    job = acquire_next_job(db_session)
    assert job is None

# --- Recovery tests ---

def test_fresh_processing_job_not_recovered(db_session: Session, queued_job: DocumentProcessingJob):
    job = acquire_next_job(db_session)
    
    # Freshly acquired, shouldn't be recovered
    recovered = recover_stale_job(db_session)
    assert recovered is None

def test_stale_processing_job_is_recovered(db_session: Session, queued_job: DocumentProcessingJob):
    job = acquire_next_job(db_session)
    
    # Make it stale
    job.started_at = datetime.utcnow() - timedelta(seconds=settings.worker_stale_job_timeout_seconds + 10)
    db_session.commit()
    
    recovered = recover_stale_job(db_session)
    assert recovered is not None
    assert recovered.id == job.id
    assert recovered.status == JobStatus.QUEUED
    assert recovered.last_error == "Recovered from stale PROCESSING state"
    assert recovered.started_at is None
    assert recovered.attempt_count == 1 # Did not increment

def test_stale_recovery_schedules_retry(db_session: Session, queued_job: DocumentProcessingJob):
    job = acquire_next_job(db_session)
    
    # Make it stale
    job.started_at = datetime.utcnow() - timedelta(seconds=settings.worker_stale_job_timeout_seconds + 10)
    db_session.commit()
    
    db_session.commit()
    
    recovered = recover_stale_job(db_session)
    assert recovered is not None
    
    # Attempt count is 1, so delay should be 5 seconds
    diff = (recovered.next_attempt_at - recovered.updated_at).total_seconds()
    assert 4 < diff < 6

def test_stale_job_at_max_attempts_becomes_failed(db_session: Session, queued_job: DocumentProcessingJob):
    queued_job.attempt_count = settings.worker_max_attempts - 1
    db_session.commit()
    
    job = acquire_next_job(db_session)
    assert job.attempt_count == settings.worker_max_attempts
    
    job.started_at = datetime.utcnow() - timedelta(seconds=settings.worker_stale_job_timeout_seconds + 10)
    db_session.commit()
    
    recovered = recover_stale_job(db_session)
    assert recovered.status == JobStatus.FAILED
    assert "max attempts exceeded" in recovered.last_error
    assert recovered.completed_at is not None

def test_two_concurrent_recoveries_cannot_recover_same_row(SessionLocal_fixture, test_document: InvoiceDocument):
    db1 = SessionLocal_fixture()
    db2 = SessionLocal_fixture()
    
    try:
        # Create a stale job
        job = DocumentProcessingJob(
            document_id=test_document.id,
            status=JobStatus.PROCESSING,
            attempt_count=1,
            started_at=datetime.utcnow() - timedelta(seconds=settings.worker_stale_job_timeout_seconds + 10)
        )
        db1.add(job)
        db1.commit()
        db1.refresh(job)
        
        results = []
        def recover_in_thread(db_sess):
            res = recover_stale_job(db_sess)
            results.append(res)
            
        t1 = threading.Thread(target=recover_in_thread, args=(db1,))
        t2 = threading.Thread(target=recover_in_thread, args=(db2,))
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # Only one should succeed
        successes = [r for r in results if r is not None]
        assert len(successes) == 1
        
    finally:
        db1.close()
        db2.close()

# --- Transaction tests ---

def test_retry_state_committed_and_visible(SessionLocal_fixture, test_document: InvoiceDocument):
    db1 = SessionLocal_fixture()
    db2 = SessionLocal_fixture()
    try:
        job = DocumentProcessingJob(
            document_id=test_document.id,
            status=JobStatus.QUEUED,
            attempt_count=0,
            next_attempt_at=datetime.utcnow() - timedelta(seconds=1)
        )
        db1.add(job)
        db1.commit()
        
        acquired = acquire_next_job(db1)
        fail_job(db1, str(acquired.id), "Fail test")
        
        # visible in db2
        job_db2 = db2.query(DocumentProcessingJob).get(acquired.id)
        assert job_db2.status == JobStatus.QUEUED
        assert job_db2.last_error == "Fail test"
        
    finally:
        db1.close()
        db2.close()

def test_recovery_state_committed_and_visible(SessionLocal_fixture, test_document: InvoiceDocument):
    db1 = SessionLocal_fixture()
    db2 = SessionLocal_fixture()
    try:
        job = DocumentProcessingJob(
            document_id=test_document.id,
            status=JobStatus.PROCESSING,
            attempt_count=1,
            started_at=datetime.utcnow() - timedelta(seconds=settings.worker_stale_job_timeout_seconds + 10)
        )
        db1.add(job)
        db1.commit()
        
        recovered = recover_stale_job(db1)
        
        job_db2 = db2.query(DocumentProcessingJob).get(recovered.id)
        assert job_db2.status == JobStatus.QUEUED
        assert job_db2.last_error == "Recovered from stale PROCESSING state"
        
    finally:
        db1.close()
        db2.close()

def test_db_failure_does_not_falsely_report_success(db_session: Session, queued_job: DocumentProcessingJob):
    # Mock commit to raise exception
    job = acquire_next_job(db_session)
    
    with patch.object(db_session, 'commit', side_effect=Exception("DB Error")):
        with pytest.raises(Exception, match="DB Error"):
            fail_job(db_session, str(job.id), "Try to fail")

