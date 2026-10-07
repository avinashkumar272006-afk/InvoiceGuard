import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Enum, ForeignKey, DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

class DocumentStatus(str, enum.Enum):
    PENDING = "PENDING"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"

class InvoiceDocument(Base):
    __tablename__ = "invoice_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus, name="documentstatus", create_type=False), nullable=False, default=DocumentStatus.PENDING)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice: Mapped[Optional["Invoice"]] = relationship("Invoice", back_populates="document")
    processing_job: Mapped[Optional["DocumentProcessingJob"]] = relationship(
        "DocumentProcessingJob", back_populates="document", uselist=False
    )
