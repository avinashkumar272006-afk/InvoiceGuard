from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)

def create_po_and_invoice():
    tax_id = f"TAX-API-REV-{uuid.uuid4().hex[:8]}"
    vendor = client.post("/api/v1/vendors/", json={"name": "API Review Vendor", "tax_id": tax_id, "contact_email": "rev@vendor.com"}).json()
    
    po_number = f"PO-API-REV-{uuid.uuid4().hex[:8]}"
    po = client.post("/api/v1/purchase-orders/", json={
        "po_number": po_number,
        "vendor_id": vendor["id"],
        "issue_date": "2023-10-01",
        "total_amount": "100.00",
        "items": [{"description": "Item A", "quantity": "10", "unit_price": "10.00", "total_price": "100.00"}]
    }).json()
    
    inv_number = f"INV-API-REV-{uuid.uuid4().hex[:8]}"
    inv = client.post("/api/v1/invoices/", json={
        "invoice_number": inv_number,
        "vendor_id": vendor["id"],
        "po_id": po["id"],
        "issue_date": "2023-10-05",
        "total_amount": "120.00", # Price mismatch creates exception
        "items": [{"description": "Item A", "quantity": "12", "unit_price": "10.00", "total_price": "120.00"}]
    }).json()
    
    # Run verify to create exceptions
    client.post(f"/api/v1/invoices/{inv['id']}/verify")
    return inv["id"]

def test_api_review_unresolved_422():
    inv_id = create_po_and_invoice()
    resp = client.post(f"/api/v1/invoices/{inv_id}/review", json={
        "status": "VERIFIED",
        "actor": "admin"
    })
    assert resp.status_code == 422

def test_api_resolve_and_review():
    inv_id = create_po_and_invoice()
    # Get exceptions
    ver_resp = client.get(f"/api/v1/invoices/{inv_id}/verification").json()
    
    # Resolve all exceptions
    for exc in ver_resp["exceptions"]:
        exc_id = exc["id"]
        resp = client.post(f"/api/v1/invoices/{inv_id}/exceptions/{exc_id}/resolve", json={"actor": "admin", "comment": "Approved"})
        assert resp.status_code == 200
    
    # Try resolving first again -> 400
    first_exc_id = ver_resp["exceptions"][0]["id"]
    resp = client.post(f"/api/v1/invoices/{inv_id}/exceptions/{first_exc_id}/resolve", json={"actor": "admin", "comment": "Approved"})
    assert resp.status_code == 400

    # Review VERIFIED
    resp = client.post(f"/api/v1/invoices/{inv_id}/review", json={"status": "VERIFIED", "actor": "admin"})
    assert resp.status_code == 200
    
    # Review DISPUTED after VERIFIED -> 400
    resp = client.post(f"/api/v1/invoices/{inv_id}/review", json={"status": "DISPUTED", "actor": "admin"})
    assert resp.status_code == 400

def test_api_audit_logs():
    inv_id = create_po_and_invoice()
    resp = client.get(f"/api/v1/invoices/{inv_id}/audit-logs")
    assert resp.status_code == 200
    assert len(resp.json()) == 0
    
    # Disputed
    client.post(f"/api/v1/invoices/{inv_id}/review", json={"status": "DISPUTED", "actor": "admin"})
    
    resp = client.get(f"/api/v1/invoices/{inv_id}/audit-logs")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["action"] == "STATUS_CHANGE"
