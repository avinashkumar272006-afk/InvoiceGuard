from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)

def create_vendor_helper():
    tax_id = f"TAX-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/vendors/",
        json={"name": "Inv Test Vendor", "tax_id": tax_id, "contact_email": "inv@vendor.com"}
    )
    return resp.json()

def test_create_invoice():
    vendor = create_vendor_helper()
    inv_number = f"INV-{uuid.uuid4().hex[:8]}"
    
    payload = {
        "invoice_number": inv_number,
        "vendor_id": vendor["id"],
        "issue_date": "2023-10-05",
        "total_amount": "200.00",
        "items": [
            {
                "description": "Consulting",
                "quantity": "2",
                "unit_price": "100.00",
                "total_price": "200.00"
            }
        ]
    }
    
    response = client.post("/api/v1/invoices/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["invoice_number"] == inv_number
    assert data["total_amount"] == "200.00"
    assert len(data["items"]) == 1
    
    return data

def test_create_duplicate_invoice():
    vendor = create_vendor_helper()
    inv_number = f"INV-{uuid.uuid4().hex[:8]}"
    
    payload = {
        "invoice_number": inv_number,
        "vendor_id": vendor["id"],
        "issue_date": "2023-10-05",
        "total_amount": "200.00",
        "items": []
    }
    
    # First should succeed
    resp1 = client.post("/api/v1/invoices/", json=payload)
    assert resp1.status_code == 201
    
    # Second should fail with 409
    resp2 = client.post("/api/v1/invoices/", json=payload)
    assert resp2.status_code == 409

def test_get_invoices():
    response = client.get("/api/v1/invoices/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_invoice_by_id():
    inv = test_create_invoice()
    
    response = client.get(f"/api/v1/invoices/{inv['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == inv["id"]
    assert data["invoice_number"] == inv["invoice_number"]

def test_get_missing_invoice():
    response = client.get("/api/v1/invoices/999999")
    assert response.status_code == 404

def test_update_invoice():
    inv = test_create_invoice()
    
    response = client.patch(
        f"/api/v1/invoices/{inv['id']}",
        json={"status": "PAID"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PAID"
    assert data["invoice_number"] == inv["invoice_number"]
