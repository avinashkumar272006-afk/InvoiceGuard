import pytest
from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)

def create_api_test_data():
    suffix = uuid.uuid4().hex[:6]
    
    # 1. Create vendor
    v_resp = client.post(
        "/api/v1/vendors/",
        json={"name": "API Vendor", "tax_id": f"TAX-API-{suffix}", "contact_email": "api@vendor.com"}
    )
    vendor_id = v_resp.json()["id"]
    
    # 2. Create PO
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
                }
            ]
        }
    )
    po_id = po_resp.json()["id"]
    
    # 3. Create Invoice
    inv_resp = client.post(
        "/api/v1/invoices/",
        json={
            "invoice_number": f"INV-API-{suffix}",
            "vendor_id": vendor_id,
            "po_id": None,
            "issue_date": "2023-10-05",
            "total_amount": "100.00",
            "items": [
                {
                    "description": "Item A",
                    "quantity": "10",
                    "unit_price": "10.00",
                    "total_price": "100.00"
                }
            ]
        }
    )
    inv_id = inv_resp.json()["id"]
    
    return vendor_id, po_id, inv_id

def test_api_invoice_linking_success():
    vendor_id, po_id, inv_id = create_api_test_data()
    
    payload = {
        "po_id": po_id,
        "actor": "api@test.com",
        "comment": "Linking via API"
    }
    
    response = client.post(f"/api/v1/invoices/{inv_id}/link-po", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["po_id"] == po_id
    assert "id" in data

def test_api_invoice_linking_missing_invoice():
    payload = {
        "po_id": 1,
        "actor": "api@test.com"
    }
    response = client.post("/api/v1/invoices/999999/link-po", json=payload)
    assert response.status_code == 404

def test_api_invoice_linking_missing_po():
    vendor_id, po_id, inv_id = create_api_test_data()
    payload = {
        "po_id": 999999,
        "actor": "api@test.com"
    }
    response = client.post(f"/api/v1/invoices/{inv_id}/link-po", json=payload)
    assert response.status_code == 404

def test_api_invoice_linking_validation_error():
    vendor_id, po_id, inv_id = create_api_test_data()
    payload = {
        "po_id": po_id,
        # missing actor
    }
    response = client.post(f"/api/v1/invoices/{inv_id}/link-po", json=payload)
    assert response.status_code == 422
