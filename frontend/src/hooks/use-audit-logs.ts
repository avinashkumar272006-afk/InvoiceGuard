import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { AuditLog } from '@/types';

export function useAuditLogs(invoiceId: number | string) {
  return useQuery({
    queryKey: ['invoice-audit-logs', String(invoiceId)],
    queryFn: () => api.get<AuditLog[]>(`/api/v1/invoices/${invoiceId}/audit-logs`),
    enabled: !!invoiceId,
  });
}
