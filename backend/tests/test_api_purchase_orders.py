from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)

def create_vendor_helper():
    tax_id = f"TAX-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/vendors/",
        json={"name": "PO Test Vendor", "tax_id": tax_id, "contact_email": "po@vendor.com"}
    )
    return resp.json()

def test_create_po():
    vendor = create_vendor_helper()
    po_number = f"PO-{uuid.uuid4().hex[:8]}"
    
    payload = {
        "po_number": po_number,
        "vendor_id": vendor["id"],
        "issue_date": "2023-10-01",
        "total_amount": "150.00",
        "items": [
            {
                "description": "Widget A",
                "quantity": "10",
                "unit_price": "10.00",
                "total_price": "100.00"
            },
            {
                "description": "Widget B",
                "quantity": "5",
                "unit_price": "10.00",
                "total_price": "50.00"
            }
        ]
    }
    
    response = client.post("/api/v1/purchase-orders/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["po_number"] == po_number
    assert data["total_amount"] == "150.00"
    assert len(data["items"]) == 2
    
    return data

def test_get_pos():
    response = client.get("/api/v1/purchase-orders/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_po_by_id():
    po = test_create_po()
    
    response = client.get(f"/api/v1/purchase-orders/{po['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == po["id"]
    assert data["po_number"] == po["po_number"]

def test_get_missing_po():
    response = client.get("/api/v1/purchase-orders/999999")
    assert response.status_code == 404

def test_update_po():
    po = test_create_po()
    
    response = client.patch(
        f"/api/v1/purchase-orders/{po['id']}",
        json={"status": "APPROVED"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["po_number"] == po["po_number"]
