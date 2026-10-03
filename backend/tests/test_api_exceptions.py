import pytest
from fastapi import status
from fastapi.testclient import TestClient
import uuid

from app.database.connection import SessionLocal, engine, get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.purchase_order import PurchaseOrder
from app.models.vendor import Vendor
from app.models.verification import Verification, InvoiceException, VerificationStatus, ExceptionType
from app.main import app

@pytest.fixture(scope="function")
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    
    app.dependency_overrides[get_db] = lambda: session
    
    # Clear exceptions before testing
    session.query(InvoiceException).delete()
    session.query(Verification).delete()
    session.commit()
    
    yield session
    
    app.dependency_overrides.clear()
    session.close()
    transaction.rollback()
    connection.close()

client = TestClient(app)

def create_test_data(db, num_resolved, num_unresolved, types_map=None):
    # Create vendor
    vendor = Vendor(
        name="Test Vendor",
        tax_id=f"TEST-{uuid.uuid4()}",
        contact_email="test@test.com",
    )
    db.add(vendor)
    db.flush()
    
    # Create PO
    po = PurchaseOrder(
        po_number=f"PO-{uuid.uuid4()}",
        vendor_id=vendor.id,
        issue_date="2026-01-01",
        total_amount=100.0,
        status="PENDING"
    )
    db.add(po)
    db.flush()

    # Create Invoice
    invoice = Invoice(
        invoice_number=f"INV-{uuid.uuid4()}",
        vendor_id=vendor.id,
        po_id=po.id,
        issue_date="2026-01-01",
        total_amount=100.0,
        status=InvoiceStatus.PENDING
    )
    db.add(invoice)
    db.flush()

    # Create Verification
    verification = Verification(
        invoice_id=invoice.id,
        status=VerificationStatus.FAILED
    )
    db.add(verification)
    db.flush()

    if types_map is None:
        types_map = {}

    exceptions = []
    # Add resolved exceptions
    for i in range(num_resolved):
        exc_type = types_map.get(f"res_{i}", ExceptionType.PRICE_MISMATCH)
        exceptions.append(InvoiceException(
            verification_id=verification.id,
            exception_type=exc_type,
            description="Test resolved exception",
            resolved=True
        ))
    
    # Add unresolved exceptions
    for i in range(num_unresolved):
        exc_type = types_map.get(f"unres_{i}", ExceptionType.QUANTITY_MISMATCH)
        exceptions.append(InvoiceException(
            verification_id=verification.id,
            exception_type=exc_type,
            description="Test unresolved exception",
            resolved=False
        ))

    db.add_all(exceptions)
    db.commit()

def test_exception_summary_empty(db_session):
    response = client.get("/api/v1/exceptions/summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 0
    assert data["resolved"] == 0
    assert data["unresolved"] == 0
    assert data["by_type"] == {}

def test_exception_summary_only_unresolved(db_session):
    create_test_data(db_session, num_resolved=0, num_unresolved=3)
    response = client.get("/api/v1/exceptions/summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 3
    assert data["resolved"] == 0
    assert data["unresolved"] == 3

def test_exception_summary_only_resolved(db_session):
    create_test_data(db_session, num_resolved=4, num_unresolved=0)
    response = client.get("/api/v1/exceptions/summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 4
    assert data["resolved"] == 4
    assert data["unresolved"] == 0

def test_exception_summary_mixed(db_session):
    types_map = {
        "res_0": ExceptionType.PRICE_MISMATCH,
        "res_1": ExceptionType.PRICE_MISMATCH,
        "unres_0": ExceptionType.QUANTITY_MISMATCH,
        "unres_1": ExceptionType.NOT_ON_PO,
        "unres_2": ExceptionType.NOT_ON_PO
    }
    create_test_data(db_session, num_resolved=2, num_unresolved=3, types_map=types_map)
    response = client.get("/api/v1/exceptions/summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 5
    assert data["resolved"] == 2
    assert data["unresolved"] == 3
    
    assert "by_type" in data
    assert data["by_type"][ExceptionType.PRICE_MISMATCH.value] == 2
    assert data["by_type"][ExceptionType.QUANTITY_MISMATCH.value] == 1
    assert data["by_type"][ExceptionType.NOT_ON_PO.value] == 2
