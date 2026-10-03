export type InvoiceStatus = 'PENDING' | 'VERIFIED' | 'DISPUTED' | 'PAID';
export type DocumentStatus = 'PENDING' | 'EXTRACTING' | 'EXTRACTED' | 'FAILED';

export interface InvoiceDocument {
  id: string; // uuid
  filename: string;
  content_type: string;
  storage_path: string;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
}

export interface InvoiceItem {
  id: number;
  invoice_id: number;
  description: string;
  quantity: string;
  unit_price: string;
  total_price: string;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  vendor_id: number;
  po_id: number | null;
  issue_date: string;
  total_amount: string;
  status: InvoiceStatus;
  items: InvoiceItem[];
  document_id: string | null;
}

export interface Vendor {
  id: number;
  name: string;
  email: string | null;
  tax_id: string | null;
  address: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type POStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'COMPLETED';

export interface PurchaseOrderItem {
  id: number;
  po_id: number;
  description: string;
  quantity: string;
  unit_price: string;
  total_price: string;
}

export interface PurchaseOrder {
  id: number;
  vendor_id: number;
  po_number: string;
  issue_date: string; // YYYY-MM-DD
  total_amount: string; // Decimal
  status: POStatus;
  items: PurchaseOrderItem[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DocumentUrlResponse {
  url: string;
  expires_in: number;
}

export type VerificationStatus = 'PASSED' | 'FAILED' | 'PENDING';
export type ExceptionType = 'PRICE_MISMATCH' | 'QUANTITY_MISMATCH' | 'NOT_ON_PO' | 'PO_NOT_FOUND' | 'MATH_ERROR';

export interface InvoiceException {
  id: number;
  verification_id: number;
  exception_type: ExceptionType;
  description: string;
  resolved: boolean;
}

export interface ExceptionResolveCreate {
  actor: string;
  comment?: string | null;
}

export interface ExceptionResolveResponse {
  id: number;
  resolved: boolean;
}

export interface ReviewCreate {
  status: 'VERIFIED' | 'DISPUTED';
  actor: string;
  comment?: string | null;
}

export interface PurchaseOrderLinkCreate {
  po_id: number;
  actor: string;
  comment?: string | null;
}

export interface AuditLog {
  id: number;
  invoice_id: number;
  actor: string;
  action: string;
  entity_name: string;
  entity_id: number | null;
  previous_state: string | null;
  new_state: string | null;
  comment: string | null;
  created_at: string;
}

export interface Verification {
  id: number;
  invoice_id: number;
  status: VerificationStatus;
  verified_at: string | null;
  exceptions: InvoiceException[];
}

export interface DocumentResponse {
  id: string;
  filename: string;
  status: DocumentStatus;
  created_at: string;
}

export interface DocumentProcessingResponse {
  success: boolean;
  message: string;
  invoice_id: number | null;
}

export interface ExceptionSummary {
  total: number;
  resolved: number;
  unresolved: number;
  by_type: Record<string, number> | null;
}
