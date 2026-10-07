import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy.orm import Session
import uuid
from decimal import Decimal

from app.main import app
from app.database.connection import engine, SessionLocal
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.invoice import Invoice, InvoiceItem
from app.models.audit import AuditLog
from app.schemas.invoice import InvoiceItemMapPO
from app.services.invoice import map_invoice_item_to_po_item, unmap_invoice_item_to_po_item

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

def create_api_test_data():
    suffix = uuid.uuid4().hex[:6]
    
    v_resp = client.post(
        "/api/v1/vendors/",
        json={"name": "API Vendor", "tax_id": f"TAX-API-{suffix}", "contact_email": "api@vendor.com"}
    )
    vendor_id = v_resp.json()["id"]
    
    po_resp = client.post(
        "/api/v1/purchase-orders/",
        json={
            "po_number": f"PO-API-{suffix}",
            "vendor_id": vendor_id,
            "issue_date": "2023-10-01",
            "total_amount": "100.00",
            "items": [
                {
                    "description": "Item A",
                    "quantity": "10",
                    "unit_price": "10.00",
                    "total_price": "100.00"
                },
                {
                    "description": "Item B",
                    "quantity": "5",
                    "unit_price": "20.00",
                    "total_price": "100.00"
                }
            ]
        }
    )
    po_data = po_resp.json()
    po_id = po_data["id"]
    po_item_a_id = po_data["items"][0]["id"]
    po_item_b_id = po_data["items"][1]["id"]
    
    po2_resp = client.post(
        "/api/v1/purchase-orders/",
        json={
            "po_number": f"PO-API2-{suffix}",
            "vendor_id": vendor_id,
            "issue_date": "2023-10-01",
            "total_amount": "100.00",
            "items": [
                {
                    "description": "Item C",
                    "quantity": "10",
                    "unit_price": "10.00",
                    "total_price": "100.00"
                }
            ]
        }
    )
    po2_data = po2_resp.json()
    po2_id = po2_data["id"]
    po2_item_id = po2_data["items"][0]["id"]

    inv_resp = client.post(
        "/api/v1/invoices/",
        json={
            "invoice_number": f"INV-API-{suffix}",
            "vendor_id": vendor_id,
            "po_id": po_id,
            "issue_date": "2023-10-05",
            "total_amount": "100.00",
            "items": [
                {
                    "description": "Invoice Item A",
                    "quantity": "10",
                    "unit_price": "10.00",
                    "total_price": "100.00"
                },
                {
                    "description": "Invoice Item B",
                    "quantity": "5",
                    "unit_price": "20.00",
                    "total_price": "100.00"
                }
            ]
        }
    )
    inv_data = inv_resp.json()
    inv_id = inv_data["id"]
    inv_item_a_id = inv_data["items"][0]["id"]
    inv_item_b_id = inv_data["items"][1]["id"]
    
    inv2_resp = client.post(
        "/api/v1/invoices/",
        json={
            "invoice_number": f"INV-API2-{suffix}",
            "vendor_id": vendor_id,
            "po_id": None,
            "issue_date": "2023-10-05",
            "total_amount": "100.00",
            "items": [
                {
                    "description": "Invoice Item C",
                    "quantity": "10",
                    "unit_price": "10.00",
                    "total_price": "100.00"
                }
            ]
        }
    )
    inv2_data = inv2_resp.json()
    inv2_id = inv2_data["id"]
    inv2_item_id = inv2_data["items"][0]["id"]

    return {
        "vendor_id": vendor_id,
        "po_id": po_id,
        "po_item_a_id": po_item_a_id,
        "po_item_b_id": po_item_b_id,
        "po2_id": po2_id,
        "po2_item_id": po2_item_id,
        "inv_id": inv_id,
        "inv_item_a_id": inv_item_a_id,
        "inv_item_b_id": inv_item_b_id,
        "inv2_id": inv2_id,
        "inv2_item_id": inv2_item_id
    }

def test_map_invoice_item_success():
    data = create_api_test_data()
    payload = {
        "po_item_id": data["po_item_a_id"],
        "actor": "Jane Doe",
        "comment": "Matched"
    }
    resp = client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/map", json=payload)
    assert resp.status_code == 200
    inv = resp.json()
    item = next(i for i in inv["items"] if i["id"] == data["inv_item_a_id"])
    assert item["po_item_id"] == data["po_item_a_id"]

    audit_resp = client.get(f"/api/v1/invoices/{data['inv_id']}/audit-logs")
    logs = audit_resp.json()
    map_logs = [log for log in logs if log["action"] == "PO_LINE_MAPPED"]
    assert len(map_logs) == 1
    assert map_logs[0]["actor"] == "Jane Doe"
    assert map_logs[0]["comment"] == "Matched"

def test_unmap_invoice_item_success():
    data = create_api_test_data()
    client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/map", json={"po_item_id": data["po_item_a_id"], "actor": "Jane Doe"})
    
    payload = {
        "actor": "John Doe",
        "comment": "Unmapped"
    }
    resp = client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/unmap", json=payload)
    assert resp.status_code == 200
    inv = resp.json()
    item = next(i for i in inv["items"] if i["id"] == data["inv_item_a_id"])
    assert item["po_item_id"] is None

    audit_resp = client.get(f"/api/v1/invoices/{data['inv_id']}/audit-logs")
    logs = audit_resp.json()
    unmap_logs = [log for log in logs if log["action"] == "PO_LINE_UNMAPPED"]
    assert len(unmap_logs) == 1
    assert unmap_logs[0]["actor"] == "John Doe"

def test_map_invoice_item_wrong_po():
    data = create_api_test_data()
    payload = {
        "po_item_id": data["po2_item_id"],
        "actor": "Jane Doe"
    }
    resp = client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/map", json=payload)
    assert resp.status_code == 422
    
    audit_resp = client.get(f"/api/v1/invoices/{data['inv_id']}/audit-logs")
    logs = audit_resp.json()
    map_logs = [log for log in logs if log["action"] == "PO_LINE_MAPPED"]
    assert len(map_logs) == 0

def test_map_invoice_item_no_po():
    data = create_api_test_data()
    payload = {
        "po_item_id": data["po_item_a_id"],
        "actor": "Jane Doe"
    }
    resp = client.post(f"/api/v1/invoices/{data['inv2_id']}/items/{data['inv2_item_id']}/map", json=payload)
    assert resp.status_code == 422
    
    audit_resp = client.get(f"/api/v1/invoices/{data['inv2_id']}/audit-logs")
    logs = audit_resp.json()
    map_logs = [log for log in logs if log["action"] == "PO_LINE_MAPPED"]
    assert len(map_logs) == 0

def test_map_invoice_item_not_found():
    data = create_api_test_data()
    payload = {
        "po_item_id": data["po_item_a_id"],
        "actor": "Jane Doe"
    }
    resp = client.post(f"/api/v1/invoices/99999/items/{data['inv_item_a_id']}/map", json=payload)
    assert resp.status_code == 404
    
    resp = client.post(f"/api/v1/invoices/{data['inv_id']}/items/99999/map", json=payload)
    assert resp.status_code == 404
    
    payload["po_item_id"] = 99999
    resp = client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/map", json=payload)
    assert resp.status_code == 404

def test_map_idempotent():
    data = create_api_test_data()
    payload = {
        "po_item_id": data["po_item_a_id"],
        "actor": "Jane Doe"
    }
    client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/map", json=payload)
    resp = client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/map", json=payload)
    assert resp.status_code == 200
    
    audit_resp = client.get(f"/api/v1/invoices/{data['inv_id']}/audit-logs")
    logs = audit_resp.json()
    map_logs = [log for log in logs if log["action"] == "PO_LINE_MAPPED"]
    assert len(map_logs) == 1

def test_already_unmapped_idempotent():
    data = create_api_test_data()
    payload = {
        "actor": "Jane Doe"
    }
    resp = client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/unmap", json=payload)
    assert resp.status_code == 200
    
    audit_resp = client.get(f"/api/v1/invoices/{data['inv_id']}/audit-logs")
    logs = audit_resp.json()
    unmap_logs = [log for log in logs if log["action"] == "PO_LINE_UNMAPPED"]
    assert len(unmap_logs) == 0

def test_remapping():
    data = create_api_test_data()
    payload = {
        "po_item_id": data["po_item_a_id"],
        "actor": "Jane Doe"
    }
    client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/map", json=payload)
    
    payload["po_item_id"] = data["po_item_b_id"]
    resp = client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/map", json=payload)
    assert resp.status_code == 200
    
    audit_resp = client.get(f"/api/v1/invoices/{data['inv_id']}/audit-logs")
    logs = audit_resp.json()
    map_logs = [log for log in logs if log["action"] == "PO_LINE_MAPPED"]
    assert len(map_logs) == 2
    assert map_logs[0]["previous_state"] == f"POItem: {data['po_item_a_id']}"
    assert map_logs[0]["new_state"] == f"POItem: {data['po_item_b_id']}"

def create_service_test_data(db: Session):
    suffix = uuid.uuid4().hex[:6]
    vendor = Vendor(name="Service Vendor", tax_id=f"TAX-S-{suffix}", contact_email="test@vendor.com")
    db.add(vendor)
    db.flush()
    
    po = PurchaseOrder(
        po_number=f"PO-S-{suffix}",
        vendor_id=vendor.id,
        issue_date="2023-10-01",
        total_amount=Decimal("100.00"),
        items=[PurchaseOrderItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    )
    db.add(po)
    db.flush()
    
    inv = Invoice(
        invoice_number=f"INV-S-{suffix}",
        vendor_id=vendor.id,
        po_id=po.id,
        issue_date="2023-10-05",
        total_amount=Decimal("100.00"),
        items=[InvoiceItem(description="Item A", quantity=Decimal("10"), unit_price=Decimal("10.00"), total_price=Decimal("100.00"))]
    )
    db.add(inv)
    db.commit()
    
    return vendor.id, po.id, po.items[0].id, inv.id, inv.items[0].id

def test_transaction_safety_mapping():
    data = create_api_test_data()
    payload = {
        "po_item_id": data["po_item_a_id"],
        "actor": "trans@test.com",
        "comment": "Should rollback"
    }
    
    with patch('app.services.invoice.verify_invoice') as mock_verify:
        mock_verify.side_effect = Exception("Verification failed horribly")
        resp = client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/map", json=payload)
        assert resp.status_code == 500
            
    # Use a new request to verify the database state remained unchanged
    resp_inv = client.get(f"/api/v1/invoices/{data['inv_id']}")
    assert resp_inv.status_code == 200
    inv = resp_inv.json()
    item = next(i for i in inv["items"] if i["id"] == data["inv_item_a_id"])
    assert item["po_item_id"] is None
    
    audit_resp = client.get(f"/api/v1/invoices/{data['inv_id']}/audit-logs")
    logs = audit_resp.json()
    map_logs = [log for log in logs if log["actor"] == "trans@test.com" and log["action"] == "PO_LINE_MAPPED"]
    assert len(map_logs) == 0

def test_transaction_safety_unmapping():
    data = create_api_test_data()
    # Map it first
    client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/map", json={"po_item_id": data["po_item_a_id"], "actor": "setup@test.com"})
    
    payload = {
        "actor": "trans_unmap@test.com",
        "comment": "Should rollback"
    }
    
    with patch('app.services.invoice.verify_invoice') as mock_verify:
        mock_verify.side_effect = Exception("Verification failed horribly")
        resp = client.post(f"/api/v1/invoices/{data['inv_id']}/items/{data['inv_item_a_id']}/unmap", json=payload)
        assert resp.status_code == 500
            
    # Use a new request to verify the database state remained unchanged
    resp_inv = client.get(f"/api/v1/invoices/{data['inv_id']}")
    assert resp_inv.status_code == 200
    inv = resp_inv.json()
    item = next(i for i in inv["items"] if i["id"] == data["inv_item_a_id"])
    assert item["po_item_id"] == data["po_item_a_id"]
    
    audit_resp = client.get(f"/api/v1/invoices/{data['inv_id']}/audit-logs")
    logs = audit_resp.json()
    unmap_logs = [log for log in logs if log["actor"] == "trans_unmap@test.com" and log["action"] == "PO_LINE_UNMAPPED"]
    assert len(unmap_logs) == 0
