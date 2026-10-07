from datetime import date
from typing import List, Optional
from decimal import Decimal
import enum

from sqlalchemy import String, Date, Numeric, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class InvoiceStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    DISPUTED = "DISPUTED"
    PAID = "PAID"

class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("vendor_id", "invoice_number", name="uq_vendor_invoice_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True)
    vendor_name_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    po_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus, name="invoicestatus", create_type=False), nullable=False, default=InvoiceStatus.PENDING, index=True)

    # Relationships
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="invoices")
    purchase_order: Mapped[Optional["PurchaseOrder"]] = relationship("PurchaseOrder")
    items: Mapped[List["InvoiceItem"]] = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    verification: Mapped[Optional["Verification"]] = relationship("Verification", back_populates="invoice", uselist=False, cascade="all, delete-orphan")
    document: Mapped[Optional["InvoiceDocument"]] = relationship("InvoiceDocument", back_populates="invoice", uselist=False, cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    po_item_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_order_items.id", ondelete="SET NULL"), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")
    po_item: Mapped[Optional["PurchaseOrderItem"]] = relationship("PurchaseOrderItem")
