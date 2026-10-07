import pytest
import threading
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.document_processing_job import DocumentProcessingJob, JobStatus
from app.models.invoice_document import InvoiceDocument, DocumentStatus
from app.services.worker import acquire_next_job
from app.database.connection import engine, SessionLocal

@pytest.fixture(scope="function")
def db_session():
    # Use real sessions for concurrency tests because we need real locking
    # and multiple concurrent connections to see committed data.
    session = SessionLocal()
    
    # Setup - delete all jobs and docs
    session.query(DocumentProcessingJob).delete()
    session.query(InvoiceDocument).delete()
    session.commit()
    
    yield session
    
    # Teardown
    session.query(DocumentProcessingJob).delete()
    session.query(InvoiceDocument).delete()
    session.commit()
    session.close()


def create_job(db: Session, status: JobStatus, next_attempt_offset_minutes=0, created_at_offset=0):
    doc = InvoiceDocument(
        filename="test.pdf",
        content_type="application/pdf",
        storage_path=f"raw/test_{time.time()}_{created_at_offset}.pdf",
        status=DocumentStatus.PENDING
    )
    db.add(doc)
    db.flush()
    
    job = DocumentProcessingJob(
        document_id=doc.id,
        status=status,
        next_attempt_at=datetime.utcnow() + timedelta(minutes=next_attempt_offset_minutes),
        created_at=datetime.utcnow() + timedelta(seconds=created_at_offset)
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def test_acquire_queued_job(db_session: Session):
    job = create_job(db_session, JobStatus.QUEUED)
    
    acquired = acquire_next_job(db_session)
    assert acquired is not None
    assert acquired.id == job.id
    assert acquired.status == JobStatus.PROCESSING
    assert acquired.started_at is not None

def test_do_not_acquire_future_job(db_session: Session):
    job = create_job(db_session, JobStatus.QUEUED, next_attempt_offset_minutes=10)
    
    acquired = acquire_next_job(db_session)
    assert acquired is None

def test_ignore_completed_job(db_session: Session):
    job = create_job(db_session, JobStatus.COMPLETED)
    
    acquired = acquire_next_job(db_session)
    assert acquired is None

def test_ignore_failed_job(db_session: Session):
    job = create_job(db_session, JobStatus.FAILED)
    
    acquired = acquire_next_job(db_session)
    assert acquired is None

def test_ordering(db_session: Session):
    # Older job created first
    job2 = create_job(db_session, JobStatus.QUEUED, created_at_offset=10)
    job1 = create_job(db_session, JobStatus.QUEUED, created_at_offset=0)
    
    acquired_1 = acquire_next_job(db_session)
    acquired_2 = acquire_next_job(db_session)
    
    assert acquired_1 is not None
    assert acquired_1.id == job1.id
    
    assert acquired_2 is not None
    assert acquired_2.id == job2.id

def test_concurrency(db_session: Session):
    # Create two queued jobs
    job1 = create_job(db_session, JobStatus.QUEUED, created_at_offset=0)
    job2 = create_job(db_session, JobStatus.QUEUED, created_at_offset=1)
    
    results = []
    
    def worker_thread(worker_id):
        # Dedicated session per thread
        thread_db = SessionLocal()
        try:
            acquired = acquire_next_job(thread_db)
            if acquired:
                results.append((worker_id, acquired.id))
        finally:
            thread_db.close()
            
    # Run multiple threads concurrently
    threads = [threading.Thread(target=worker_thread, args=(i,)) for i in range(4)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    # Exactly 2 jobs should be acquired
    assert len(results) == 2
    
    # They should be distinct jobs
    acquired_ids = set(r[1] for r in results)
    assert acquired_ids == {job1.id, job2.id}
    
    # Check DB state
    db_session.expire_all()
    jobs_in_db = db_session.query(DocumentProcessingJob).all()
    for j in jobs_in_db:
        assert j.status == JobStatus.PROCESSING

def test_transaction_boundary(db_session: Session):
    job = create_job(db_session, JobStatus.QUEUED)
    
    # Acquire using a temporary session to mimic worker
    temp_db = SessionLocal()
    acquired = acquire_next_job(temp_db)
    temp_db.close()  # Transaction boundary ends here!
    
    # Now check in main session
    db_session.expire_all()
    db_job = db_session.query(DocumentProcessingJob).get(job.id)
    assert db_job.status == JobStatus.PROCESSING
    assert db_job.started_at is not None

def test_no_processing_side_effects(db_session: Session):
    job = create_job(db_session, JobStatus.QUEUED)
    
    # Before acquisition
    from app.models.invoice import Invoice
    from app.models.verification import Verification
    invoice_count_before = db_session.query(Invoice).count()
    verif_count_before = db_session.query(Verification).count()
    
    # Acquire
    acquire_next_job(db_session)
    
    # Verify no invoices or verifications were created
    assert db_session.query(Invoice).count() == invoice_count_before
    assert db_session.query(Verification).count() == verif_count_before
