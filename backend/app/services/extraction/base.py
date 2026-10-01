from abc import ABC, abstractmethod
from typing import Optional
from app.schemas.extraction import ExtractedInvoiceSchema

class BaseInvoiceExtractor(ABC):
    @abstractmethod
    def extract_invoice(self, document_bytes: bytes, content_type: str, filename: Optional[str] = None) -> ExtractedInvoiceSchema:
        """Extract invoice data from document bytes."""
        pass
