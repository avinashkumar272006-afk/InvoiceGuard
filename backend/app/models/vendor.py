from datetime import datetime
from typing import List

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database.base import Base

class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    purchase_orders: Mapped[List["PurchaseOrder"]] = relationship("PurchaseOrder", back_populates="vendor")
    invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="vendor")
