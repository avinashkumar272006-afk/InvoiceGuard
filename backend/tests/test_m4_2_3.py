import pytest
from decimal import Decimal
from datetime import date
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem, POStatus
from app.models.vendor import Vendor
from app.models.verification import Verification, InvoiceException, ExceptionType, VerificationStatus
from app.services.verification import verify_invoice
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

def setup_basic_data(db_session):
    vendor = Vendor(name="Test Vendor M423")
    db_session.add(vendor)
    db_session.flush()

    po = PurchaseOrder(
        po_number="PO-M423-001",
        vendor_id=vendor.id,
        issue_date=date.today(),
        total_amount=Decimal("100.00"),
        status=POStatus.PENDING
    )
    db_session.add(po)
    db_session.flush()

    po_item1 = PurchaseOrderItem(
        po_id=po.id,
        description="PO Item 1",
        quantity=Decimal("10"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("100.00")
    )
    db_session.add(po_item1)
    db_session.flush()

    invoice = Invoice(
        invoice_number="INV-M423-001",
        vendor_id=vendor.id,
        po_id=po.id,
        issue_date=date.today(),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.PENDING,
        vendor_name_raw="Test Vendor M423"
    )
    db_session.add(invoice)
    db_session.flush()

    return po, invoice, po_item1

def test_1_persisted_mapping_wins(db_session):
    po, invoice, po_item1 = setup_basic_data(db_session)
    
    # Invoice description differs from PO description, but po_item_id is explicitly set
    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="Completely Different Description",
        quantity=Decimal("10"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("100.00"),
        po_item_id=po_item1.id
    )
    db_session.add(inv_item)
    db_session.flush()

    verification = verify_invoice(db_session, invoice.id)
    
    # Should NOT have NOT_ON_PO exception
    exceptions = verification.exceptions
    assert not any(e.exception_type == ExceptionType.NOT_ON_PO for e in exceptions)
    assert verification.status == VerificationStatus.PASSED

def test_2_wrong_po_mapping(db_session):
    po, invoice, po_item1 = setup_basic_data(db_session)

    # Another PO
    po2 = PurchaseOrder(po_number="PO-M423-002", vendor_id=po.vendor_id, issue_date=date.today(), total_amount=Decimal("50.00"), status=POStatus.PENDING)
    db_session.add(po2)
    db_session.flush()
    po2_item = PurchaseOrderItem(po_id=po2.id, description="PO2 Item", quantity=Decimal("5"), unit_price=Decimal("10.00"), total_price=Decimal("50.00"))
    db_session.add(po2_item)
    db_session.flush()

    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="PO2 Item",
        quantity=Decimal("10"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("100.00"),
        po_item_id=po2_item.id # Mapping to another PO
    )
    db_session.add(inv_item)
    db_session.flush()

    verification = verify_invoice(db_session, invoice.id)
    
    exceptions = verification.exceptions
    assert len(exceptions) >= 1
    assert any(e.exception_type == ExceptionType.NOT_ON_PO for e in exceptions)
    # `po_item_id` should not be modified
    assert inv_item.po_item_id == po2_item.id

def test_3_exact_description_matching(db_session):
    po, invoice, po_item1 = setup_basic_data(db_session)
    
    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="PO Item 1", # Exact match
        quantity=Decimal("10"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("100.00"),
        po_item_id=None
    )
    db_session.add(inv_item)
    db_session.flush()

    verification = verify_invoice(db_session, invoice.id)
    
    exceptions = verification.exceptions
    assert len(exceptions) == 0
    assert inv_item.po_item_id is None # Must not persist automatically

def test_4_normalized_description_matching(db_session):
    po, invoice, po_item1 = setup_basic_data(db_session)
    
    # " PO Item 1 " -> "po item 1" vs "PO Item 1" -> "po item 1"
    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description=" po  Item-1. ",
        quantity=Decimal("10"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("100.00"),
        po_item_id=None
    )
    db_session.add(inv_item)
    db_session.flush()

    verification = verify_invoice(db_session, invoice.id)
    
    exceptions = verification.exceptions
    assert len(exceptions) == 0
    assert inv_item.po_item_id is None

def test_5_ambiguous_normalized_match(db_session):
    po, invoice, po_item1 = setup_basic_data(db_session)
    
    # Add a duplicate PO item with same normalized description
    po_item2 = PurchaseOrderItem(
        po_id=po.id,
        description="po item 1",
        quantity=Decimal("5"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("50.00")
    )
    db_session.add(po_item2)
    
    # Update PO total
    po.total_amount = Decimal("150.00")
    invoice.total_amount = Decimal("150.00")
    
    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="pO Item-1",
        quantity=Decimal("15"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("150.00"),
        po_item_id=None
    )
    db_session.add(inv_item)
    db_session.flush()

    verification = verify_invoice(db_session, invoice.id)
    exceptions = verification.exceptions
    
    # Since it matches both po_item1 and po_item2 normalized, it should NOT auto-map to either.
    # Therefore, NOT_ON_PO
    assert any(e.exception_type == ExceptionType.NOT_ON_PO for e in exceptions)
    assert inv_item.po_item_id is None

def test_6_duplicate_po_descriptions(db_session):
    # Old dict collision bug check
    po, invoice, po_item1 = setup_basic_data(db_session)
    
    po_item2 = PurchaseOrderItem(
        po_id=po.id,
        description="PO Item 1",
        quantity=Decimal("5"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("50.00")
    )
    db_session.add(po_item2)
    po.total_amount = Decimal("150.00")
    invoice.total_amount = Decimal("150.00")
    
    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="PO Item 1",
        quantity=Decimal("15"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("150.00"),
        po_item_id=None
    )
    db_session.add(inv_item)
    db_session.flush()

    verification = verify_invoice(db_session, invoice.id)
    assert any(e.exception_type == ExceptionType.NOT_ON_PO for e in verification.exceptions)

def test_7_multiple_invoice_items_one_po_item(db_session):
    po, invoice, po_item1 = setup_basic_data(db_session)
    
    inv_item1 = InvoiceItem(
        invoice_id=invoice.id,
        description="PO Item 1",
        quantity=Decimal("6"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("60.00"),
        po_item_id=po_item1.id
    )
    inv_item2 = InvoiceItem(
        invoice_id=invoice.id,
        description="PO Item 1 (cont.)",
        quantity=Decimal("7"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("70.00"),
        po_item_id=po_item1.id
    )
    db_session.add_all([inv_item1, inv_item2])
    invoice.total_amount = Decimal("130.00")
    db_session.flush()

    verification = verify_invoice(db_session, invoice.id)
    exceptions = verification.exceptions
    
    # 6 + 7 = 13 > 10. Should have exactly one QUANTITY_MISMATCH exception
    qty_exceptions = [e for e in exceptions if e.exception_type == ExceptionType.QUANTITY_MISMATCH]
    assert len(qty_exceptions) == 1
    # Check attribution (should belong to first mapped invoice item by ID)
    primary_id = min(inv_item1.id, inv_item2.id)
    assert qty_exceptions[0].line_item_id == primary_id
    assert "Aggregated invoice quantity (13)" in qty_exceptions[0].description

def test_8_mapped_price_mismatch(db_session):
    po, invoice, po_item1 = setup_basic_data(db_session)
    
    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="Different Name",
        quantity=Decimal("10"),
        unit_price=Decimal("12.00"), # Price mismatch
        total_price=Decimal("120.00"),
        po_item_id=po_item1.id
    )
    db_session.add(inv_item)
    invoice.total_amount = Decimal("120.00")
    db_session.flush()

    verification = verify_invoice(db_session, invoice.id)
    exceptions = verification.exceptions
    
    # Should have PRICE_MISMATCH for line, not NOT_ON_PO
    assert any(e.exception_type == ExceptionType.PRICE_MISMATCH and e.line_item_id == inv_item.id for e in exceptions)
    assert not any(e.exception_type == ExceptionType.NOT_ON_PO for e in exceptions)

def test_9_stale_not_on_po_removed(db_session):
    po, invoice, po_item1 = setup_basic_data(db_session)
    
    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="Random Item",
        quantity=Decimal("10"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("100.00"),
        po_item_id=None
    )
    db_session.add(inv_item)
    db_session.flush()

    # Step 1: Run verification without mapping
    verification = verify_invoice(db_session, invoice.id)
    assert any(e.exception_type == ExceptionType.NOT_ON_PO for e in verification.exceptions)
    
    # Step 2: Establish mapping
    inv_item.po_item_id = po_item1.id
    db_session.flush()
    
    # Step 3: Verify again
    verification = verify_invoice(db_session, invoice.id)
    assert not any(e.exception_type == ExceptionType.NOT_ON_PO for e in verification.exceptions)

def test_10_resolved_exception_preserved(db_session):
    po, invoice, po_item1 = setup_basic_data(db_session)
    
    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="PO Item 1",
        quantity=Decimal("15"), # Mismatch
        unit_price=Decimal("10.00"),
        total_price=Decimal("150.00"),
        po_item_id=po_item1.id
    )
    db_session.add(inv_item)
    invoice.total_amount = Decimal("150.00")
    db_session.commit()
    db_session.expire_all()

    verification = verify_invoice(db_session, invoice.id)
    print("FIRST RUN EXCEPTIONS:")
    for e in verification.exceptions:
        print(f" - {e.exception_type}: {e.description} (resolved: {e.resolved})")
    qty_exc = next(e for e in verification.exceptions if e.exception_type == ExceptionType.QUANTITY_MISMATCH)
    
    # Resolve it manually
    qty_exc.resolved = True
    db_session.commit()
    
    # Run again
    verification = verify_invoice(db_session, invoice.id)
    print("SECOND RUN EXCEPTIONS:")
    for e in verification.exceptions:
        print(f" - {e.exception_type}: {e.description} (resolved: {e.resolved})")
    qty_exc_again = next(e for e in verification.exceptions if e.exception_type == ExceptionType.QUANTITY_MISMATCH)
    assert qty_exc_again.resolved == True

def test_11_idempotency(db_session):
    po, invoice, po_item1 = setup_basic_data(db_session)
    
    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="PO Item 1",
        quantity=Decimal("15"), # quantity mismatch
        unit_price=Decimal("10.00"),
        total_price=Decimal("150.00"),
        po_item_id=po_item1.id
    )
    db_session.add(inv_item)
    invoice.total_amount = Decimal("150.00")
    db_session.flush()

    v1 = verify_invoice(db_session, invoice.id)
    num_exc1 = len(v1.exceptions)
    
    v2 = verify_invoice(db_session, invoice.id)
    num_exc2 = len(v2.exceptions)
    
    assert num_exc1 == num_exc2

def test_12_deleted_po_item_fallback(db_session):
    po, invoice, po_item1 = setup_basic_data(db_session)
    
    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        description="Some Old Item",
        quantity=Decimal("10"),
        unit_price=Decimal("10.00"),
        total_price=Decimal("100.00"),
        po_item_id=po_item1.id
    )
    db_session.add(inv_item)
    db_session.commit()
    
    # Delete PO item
    db_session.delete(po_item1)
    db_session.commit()
    
    # Because of ON DELETE SET NULL, inv_item.po_item_id should now be NULL in the DB
    db_session.refresh(inv_item)
    assert inv_item.po_item_id is None
    
    verification = verify_invoice(db_session, invoice.id)
    # It falls back to unmapped detection, should not find "Some Old Item"
    assert any(e.exception_type == ExceptionType.NOT_ON_PO for e in verification.exceptions)
