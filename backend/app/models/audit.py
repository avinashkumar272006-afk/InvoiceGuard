from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=True)
    previous_state: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    new_state: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice")
