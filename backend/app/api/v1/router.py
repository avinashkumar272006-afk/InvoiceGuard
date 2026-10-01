from fastapi import APIRouter
from app.api.v1 import vendors, purchase_orders, invoices, documents

api_router = APIRouter()

api_router.include_router(vendors.router, prefix="/vendors", tags=["Vendors"])
api_router.include_router(purchase_orders.router, prefix="/purchase-orders", tags=["Purchase Orders"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["Invoices"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
