from datetime import datetime
from typing import List
import enum

from sqlalchemy import String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database.base import Base

class VerificationStatus(str, enum.Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING = "PENDING"

class ExceptionType(str, enum.Enum):
    PRICE_MISMATCH = "PRICE_MISMATCH"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    NOT_ON_PO = "NOT_ON_PO"
    PO_NOT_FOUND = "PO_NOT_FOUND"
    MATH_ERROR = "MATH_ERROR"
    VENDOR_UNRESOLVED = "VENDOR_UNRESOLVED"

class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    status: Mapped[VerificationStatus] = mapped_column(Enum(VerificationStatus, name="verificationstatus", create_type=False), nullable=False, default=VerificationStatus.PENDING, index=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="verification")
    exceptions: Mapped[List["InvoiceException"]] = relationship("InvoiceException", back_populates="verification", cascade="all, delete-orphan")


class InvoiceException(Base):
    __tablename__ = "invoice_exceptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    verification_id: Mapped[int] = mapped_column(ForeignKey("verifications.id", ondelete="CASCADE"), nullable=False, index=True)
    line_item_id: Mapped[int | None] = mapped_column(ForeignKey("invoice_items.id", ondelete="CASCADE"), nullable=True, index=True)
    exception_type: Mapped[ExceptionType] = mapped_column(Enum(ExceptionType, name="exceptiontype", create_type=False), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    verification: Mapped["Verification"] = relationship("Verification", back_populates="exceptions")
    line_item: Mapped["InvoiceItem"] = relationship("InvoiceItem")
