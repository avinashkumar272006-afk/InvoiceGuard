from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)

def create_po_and_invoice():
    # 1. Vendor
    tax_id = f"TAX-{uuid.uuid4().hex[:8]}"
    vendor = client.post(
        "/api/v1/vendors/",
        json={"name": "Verify API Vendor", "tax_id": tax_id, "contact_email": "verify@vendor.com"}
    ).json()
    
    # 2. PO
    po_number = f"PO-{uuid.uuid4().hex[:8]}"
    po = client.post("/api/v1/purchase-orders/", json={
        "po_number": po_number,
        "vendor_id": vendor["id"],
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
    }).json()
    
    # 3. Invoice
    inv_number = f"INV-{uuid.uuid4().hex[:8]}"
    inv = client.post("/api/v1/invoices/", json={
        "invoice_number": inv_number,
        "vendor_id": vendor["id"],
        "po_id": po["id"],
        "issue_date": "2023-10-05",
        "total_amount": "120.00", # Price mismatch
        "items": [
            {
                "description": "Item A",
                "quantity": "12", # Quantity mismatch
                "unit_price": "10.00",
                "total_price": "120.00"
            }
        ]
    }).json()
    
    return inv["id"]

def test_api_verify_invoice():
    inv_id = create_po_and_invoice()
    
    # Trigger verify
    response = client.post(f"/api/v1/invoices/{inv_id}/verify")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    assert len(data["exceptions"]) > 0
    
def test_api_get_verification():
    inv_id = create_po_and_invoice()
    client.post(f"/api/v1/invoices/{inv_id}/verify")
    
    response = client.get(f"/api/v1/invoices/{inv_id}/verification")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    
def test_api_verification_not_found():
    # An invoice exists but not verified
    tax_id = f"TAX-{uuid.uuid4().hex[:8]}"
    vendor = client.post(
        "/api/v1/vendors/",
        json={"name": "Verify API Vendor 2", "tax_id": tax_id, "contact_email": "verify2@vendor.com"}
    ).json()
    inv_number = f"INV-{uuid.uuid4().hex[:8]}"
    inv = client.post("/api/v1/invoices/", json={
        "invoice_number": inv_number,
        "vendor_id": vendor["id"],
        "issue_date": "2023-10-05",
        "total_amount": "100.00",
        "items": []
    }).json()
    
    response = client.get(f"/api/v1/invoices/{inv['id']}/verification")
    assert response.status_code == 404

def test_api_verify_missing_invoice():
    response = client.post("/api/v1/invoices/999999/verify")
    assert response.status_code == 404
