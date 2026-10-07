import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.document_processing_job import DocumentProcessingJob, JobStatus
from app.database.connection import SessionLocal
from app.core.config import settings

logger = logging.getLogger(__name__)

def acquire_next_job(db: Session) -> DocumentProcessingJob | None:
    """
    Acquires the next eligible document processing job.
    Uses FOR UPDATE SKIP LOCKED to ensure safe concurrent acquisition.
    """
    stmt = (
        select(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.status == JobStatus.QUEUED,
            DocumentProcessingJob.next_attempt_at <= datetime.utcnow()
        )
        .order_by(DocumentProcessingJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    
    job = db.execute(stmt).scalar_one_or_none()
    
    if job:
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        job.attempt_count += 1
        db.commit()
        db.refresh(job)
        return job
        
    db.rollback()
    return None

def fail_job(db: Session, job_id: str, error_message: str):
    """
    Marks a job as failed and schedules a retry if attempts remain.
    """
    stmt = select(DocumentProcessingJob).where(DocumentProcessingJob.id == job_id).with_for_update()
    job = db.execute(stmt).scalar_one_or_none()
    
    if not job:
        db.rollback()
        return

    job.last_error = error_message
    
    if job.attempt_count < settings.worker_max_attempts:
        job.status = JobStatus.QUEUED
        job.started_at = None
        
        # Calculate exponential backoff
        delay_seconds = settings.worker_retry_base_delay_seconds * (2 ** (job.attempt_count - 1))
        delay_seconds = min(delay_seconds, settings.worker_retry_max_delay_seconds)
        
        job.next_attempt_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
    else:
        job.status = JobStatus.FAILED
        job.completed_at = datetime.utcnow()

    db.commit()

def recover_stale_job(db: Session) -> DocumentProcessingJob | None:
    """
    Recovers a single stale PROCESSING job.
    Uses FOR UPDATE SKIP LOCKED to avoid concurrent recovery races.
    """
    stale_threshold = datetime.utcnow() - timedelta(seconds=settings.worker_stale_job_timeout_seconds)
    
    stmt = (
        select(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.status == JobStatus.PROCESSING,
            DocumentProcessingJob.started_at <= stale_threshold
        )
        .order_by(DocumentProcessingJob.started_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    
    job = db.execute(stmt).scalar_one_or_none()
    
    if not job:
        db.rollback()
        return None

    job.last_error = "Recovered from stale PROCESSING state"
    
    if job.attempt_count < settings.worker_max_attempts:
        job.status = JobStatus.QUEUED
        job.started_at = None
        
        # Delay based on current attempt_count (do NOT increment attempt_count on recovery)
        delay_seconds = settings.worker_retry_base_delay_seconds * (2 ** max(0, job.attempt_count - 1))
        delay_seconds = min(delay_seconds, settings.worker_retry_max_delay_seconds)
        job.next_attempt_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
    else:
        job.status = JobStatus.FAILED
        job.last_error = "Recovered from stale PROCESSING state but max attempts exceeded"
        job.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(job)
    return job

def _acquire_job_safe() -> DocumentProcessingJob | None:
    """Helper to run acquisition with its own session."""
    db = SessionLocal()
    try:
        job = acquire_next_job(db)
        if job:
            db.expunge(job)  # Detach from session so it can be safely used after close
        return job
    finally:
        db.close()

def _fail_job_safe(job_id: str, error_message: str):
    db = SessionLocal()
    try:
        fail_job(db, job_id, error_message)
    finally:
        db.close()

def _recover_stale_job_safe() -> DocumentProcessingJob | None:
    db = SessionLocal()
    try:
        job = recover_stale_job(db)
        if job:
            db.expunge(job)
        return job
    finally:
        db.close()

async def run_worker_loop():
    """Background loop that polls for eligible processing jobs."""
    logger.info("worker_started", extra={"poll_interval": settings.worker_poll_interval_seconds})
    
    try:
        while True:
            try:
                # 1. Recover one stale job if available
                recovered_job = await asyncio.to_thread(_recover_stale_job_safe)
                if recovered_job:
                    logger.info(
                        "stale_job_recovered",
                        extra={
                            "job_id": str(recovered_job.id),
                            "status": recovered_job.status.value,
                        }
                    )
                
                # 2. Acquire new job
                job = await asyncio.to_thread(_acquire_job_safe)
                
                if job:
                    logger.info(
                        "job_acquired",
                        extra={
                            "job_id": str(job.id),
                            "document_id": str(job.document_id)
                        }
                    )
                    logger.info(
                        "job_transitioned_to_processing",
                        extra={
                            "job_id": str(job.id),
                            "document_id": str(job.document_id),
                            "started_at": job.started_at.isoformat() if job.started_at else None
                        }
                    )
                    
                    # Conceptual processing boundary (not yet implemented)
                    # try:
                    #     await process_document(job)
                    # except Exception as e:
                    #     await asyncio.to_thread(_fail_job_safe, job.id, str(e))
                    
                    # Yield slightly so the loop doesn't monopolize the thread
                    await asyncio.sleep(0)
                elif not recovered_job:
                    # Sleep only if we didn't recover a job AND didn't acquire a new one
                    await asyncio.sleep(settings.worker_poll_interval_seconds)
                else:
                    # Yield slightly before continuing the loop since we did work (recovery)
                    await asyncio.sleep(0)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("worker_error", extra={"error": str(e)})
                await asyncio.sleep(settings.worker_poll_interval_seconds)
                
    except asyncio.CancelledError:
        logger.info("worker_stopped", extra={"reason": "cancelled"})
    except Exception as e:
        logger.info("worker_stopped", extra={"reason": "error", "error": str(e)})
