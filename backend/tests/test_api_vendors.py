from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_vendor():
    # Use a unique tax_id to avoid conflicts
    import uuid
    tax_id = f"TAX-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/vendors/",
        json={"name": "API Vendor", "tax_id": tax_id, "contact_email": "api@vendor.com"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API Vendor"
    assert data["tax_id"] == tax_id
    assert "id" in data
    
    return data

def test_create_duplicate_vendor():
    import uuid
    tax_id = f"TAX-{uuid.uuid4().hex[:8]}"
    payload = {"name": "API Vendor 2", "tax_id": tax_id, "contact_email": "api2@vendor.com"}
    
    # First creation should succeed
    resp1 = client.post("/api/v1/vendors/", json=payload)
    assert resp1.status_code == 201
    
    # Second creation should fail
    resp2 = client.post("/api/v1/vendors/", json=payload)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"].lower()

def test_get_vendors():
    response = client.get("/api/v1/vendors/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_vendor_by_id():
    # Create one first
    vendor = test_create_vendor()
    
    response = client.get(f"/api/v1/vendors/{vendor['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == vendor["id"]
    assert data["tax_id"] == vendor["tax_id"]

def test_get_missing_vendor():
    response = client.get("/api/v1/vendors/999999")
    assert response.status_code == 404

def test_update_vendor():
    vendor = test_create_vendor()
    
    response = client.patch(
        f"/api/v1/vendors/{vendor['id']}",
        json={"name": "Updated API Vendor"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated API Vendor"
    assert data["tax_id"] == vendor["tax_id"]  # Unchanged
