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

def test_api_link_vendor_success():
    vendor_id, po_id, inv_id = create_api_test_data()
    
    # Make invoice vendor_id None for testing
    # Since we can't easily do it via API, we just relink to another vendor
    v_resp = client.post(
        "/api/v1/vendors/",
        json={"name": "API Vendor 2", "tax_id": f"TAX-API2-{uuid.uuid4().hex[:6]}", "contact_email": "api2@vendor.com"}
    )
    new_vendor_id = v_resp.json()["id"]
    
    payload = {
        "vendor_id": new_vendor_id,
        "actor": "api@test.com",
        "comment": "Linking vendor via API"
    }
    
    response = client.post(f"/api/v1/invoices/{inv_id}/link-vendor", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["vendor_id"] == new_vendor_id

def test_api_link_vendor_missing_invoice():
    payload = {
        "vendor_id": 1,
        "actor": "api@test.com"
    }
    response = client.post("/api/v1/invoices/999999/link-vendor", json=payload)
    assert response.status_code == 404

def test_api_link_vendor_missing_vendor():
    vendor_id, po_id, inv_id = create_api_test_data()
    payload = {
        "vendor_id": 999999,
        "actor": "api@test.com"
    }
    response = client.post(f"/api/v1/invoices/{inv_id}/link-vendor", json=payload)
    assert response.status_code == 404

def test_api_link_vendor_validation_error():
    vendor_id, po_id, inv_id = create_api_test_data()
    payload = {
        "vendor_id": vendor_id,
        "actor": "" # empty actor fails min_length=1
    }
    response = client.post(f"/api/v1/invoices/{inv_id}/link-vendor", json=payload)
    assert response.status_code == 422

def test_api_link_vendor_duplicate_collision():
    vendor_id, po_id, inv_id = create_api_test_data()
    
    # We need to simulate a collision. 
    # That happens when linking an invoice (that has vendor=NULL) to a vendor where an invoice with the same number already exists.
    # We will create an invoice with no vendor.
    inv_num = f"INV-COLL-{uuid.uuid4().hex[:6]}"
    
    # 1. Invoice A with Vendor V1
    inv_a_resp = client.post(
        "/api/v1/invoices/",
        json={
            "invoice_number": inv_num,
            "vendor_id": vendor_id,
            "po_id": None,
            "issue_date": "2023-10-05",
            "total_amount": "100.00",
            "items": [{"description": "Item A", "quantity": "1", "unit_price": "100.00", "total_price": "100.00"}]
        }
    )
    
    # 2. Invoice B with Vendor NULL (using API directly, wait, API might not allow NULL vendor_id initially)
    # Actually, InvoiceCreate allows vendor_id: Optional[int] = None.
    inv_b_resp = client.post(
        "/api/v1/invoices/",
        json={
            "invoice_number": inv_num,
            "vendor_id": None,
            "po_id": None,
            "issue_date": "2023-10-05",
            "total_amount": "100.00",
            "items": [{"description": "Item A", "quantity": "1", "unit_price": "100.00", "total_price": "100.00"}]
        }
    )
    inv_b_id = inv_b_resp.json()["id"]
    
    # 3. Link Invoice B to Vendor V1 -> COLLISION (409)
    payload = {
        "vendor_id": vendor_id,
        "actor": "api@test.com"
    }
    response = client.post(f"/api/v1/invoices/{inv_b_id}/link-vendor", json=payload)
    assert response.status_code == 409
