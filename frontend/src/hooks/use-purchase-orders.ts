import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { PurchaseOrder } from '@/types';

export function usePurchaseOrders(skip = 0, limit = 100) {
  return useQuery({
    queryKey: ['purchase-orders', skip, limit],
    queryFn: () => api.get<PurchaseOrder[]>(`/api/v1/purchase-orders/?skip=${skip}&limit=${limit}`),
  });
}
