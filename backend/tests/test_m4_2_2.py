import pytest
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
from datetime import date
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem, POStatus
from app.models.vendor import Vendor
from app.database.connection import engine, SessionLocal

@pytest.fixture(scope="function")
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

def test_invoice_item_po_item_id_nullable(db_session):
    vendor = Vendor(name="Test Vendor 1")
    db_session.add(vendor)
    db_session.commit()

    invoice = Invoice(
        invoice_number="INV-1",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.PENDING
    )
    db_session.add(invoice)
    db_session.commit()

    item = InvoiceItem(
        invoice_id=invoice.id,
        description="Test Item",
        quantity=Decimal("1.0"),
        unit_price=Decimal("100.00"),
        total_price=Decimal("100.00"),
        po_item_id=None
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    assert item.id is not None
    assert item.po_item_id is None

def test_invoice_item_references_valid_po_item(db_session):
    vendor = Vendor(name="Test Vendor 2")
    db_session.add(vendor)
    db_session.commit()

    po = PurchaseOrder(
        po_number="PO-1",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("100.00"),
        status=POStatus.PENDING
    )
    db_session.add(po)
    db_session.commit()

    po_item = PurchaseOrderItem(
        po_id=po.id,
        description="PO Item",
        quantity=Decimal("1.0"),
        unit_price=Decimal("100.00"),
        total_price=Decimal("100.00")
    )
    db_session.add(po_item)
    db_session.commit()

    invoice = Invoice(
        invoice_number="INV-2",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.PENDING
    )
    db_session.add(invoice)
    db_session.commit()

    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="Inv Item",
        quantity=Decimal("1.0"),
        unit_price=Decimal("100.00"),
        total_price=Decimal("100.00"),
        po_item_id=po_item.id
    )
    db_session.add(inv_item)
    db_session.commit()
    db_session.refresh(inv_item)

    assert inv_item.po_item_id == po_item.id
    assert inv_item.po_item is not None
    assert inv_item.po_item.id == po_item.id

def test_delete_po_item_sets_invoice_item_po_item_id_to_null(db_session):
    vendor = Vendor(name="Test Vendor 3")
    db_session.add(vendor)
    db_session.commit()

    po = PurchaseOrder(
        po_number="PO-2",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("100.00"),
        status=POStatus.PENDING
    )
    db_session.add(po)
    db_session.commit()

    po_item = PurchaseOrderItem(
        po_id=po.id,
        description="PO Item",
        quantity=Decimal("1.0"),
        unit_price=Decimal("100.00"),
        total_price=Decimal("100.00")
    )
    db_session.add(po_item)
    db_session.commit()

    invoice = Invoice(
        invoice_number="INV-3",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.PENDING
    )
    db_session.add(invoice)
    db_session.commit()

    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="Inv Item",
        quantity=Decimal("1.0"),
        unit_price=Decimal("100.00"),
        total_price=Decimal("100.00"),
        po_item_id=po_item.id
    )
    db_session.add(inv_item)
    db_session.commit()

    # Delete the referenced PurchaseOrderItem
    db_session.delete(po_item)
    db_session.commit()

    db_session.refresh(inv_item)
    assert inv_item.po_item_id is None
    assert inv_item.id is not None # InvoiceItem is NOT deleted

def test_invalid_po_item_id_fk(db_session):
    vendor = Vendor(name="Test Vendor 4")
    db_session.add(vendor)
    db_session.commit()

    invoice = Invoice(
        invoice_number="INV-4",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.PENDING
    )
    db_session.add(invoice)
    db_session.commit()

    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="Inv Item",
        quantity=Decimal("1.0"),
        unit_price=Decimal("100.00"),
        total_price=Decimal("100.00"),
        po_item_id=999999 # Invalid ID
    )
    db_session.add(inv_item)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
