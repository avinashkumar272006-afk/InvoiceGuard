import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Enum, ForeignKey, DateTime, Uuid, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoice_documents.id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="jobstatus", create_type=False), nullable=False, default=JobStatus.QUEUED)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document: Mapped["InvoiceDocument"] = relationship("InvoiceDocument", back_populates="processing_job")

    __table_args__ = (
        Index("ix_document_processing_jobs_status_next_attempt", "status", "next_attempt_at"),
    )
