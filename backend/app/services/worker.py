import asyncio
import logging
from datetime import datetime
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
        db.commit()
        db.refresh(job)
        return job
        
    db.rollback()
    return None

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

async def run_worker_loop():
    """Background loop that polls for eligible processing jobs."""
    logger.info("worker_started", extra={"poll_interval": settings.worker_poll_interval_seconds})
    
    try:
        while True:
            try:
                # Run sync DB logic in thread pool to avoid blocking FastAPI event loop
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
                    # Hand off document processing here in future milestones
                    
                    # Yield slightly so the loop doesn't monopolize the thread
                    await asyncio.sleep(0)
                else:
                    await asyncio.sleep(settings.worker_poll_interval_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("worker_error", extra={"error": str(e)})
                await asyncio.sleep(settings.worker_poll_interval_seconds)
                
    except asyncio.CancelledError:
        logger.info("worker_stopped", extra={"reason": "cancelled"})
    except Exception as e:
        logger.info("worker_stopped", extra={"reason": "error", "error": str(e)})
