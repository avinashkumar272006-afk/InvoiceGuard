import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Invoice } from '@/types';

export function useInvoices(skip = 0, limit = 100) {
  return useQuery({
    queryKey: ['invoices', skip, limit],
    queryFn: () => api.get<Invoice[]>(`/api/v1/invoices/?skip=${skip}&limit=${limit}`),
  });
}
