from datetime import date
from typing import List
from decimal import Decimal
import enum

from sqlalchemy import String, Date, Numeric, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class POStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FULFILLED = "FULFILLED"

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False, index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    status: Mapped[POStatus] = mapped_column(Enum(POStatus, name="postatus", create_type=False), nullable=False, default=POStatus.PENDING, index=True)

    # Relationships
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="purchase_orders")
    items: Mapped[List["PurchaseOrderItem"]] = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="items")
