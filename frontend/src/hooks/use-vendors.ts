import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Vendor } from '@/types';

export function useVendors() {
  return useQuery({
    queryKey: ['vendors'],
    queryFn: () => api.get<Vendor[]>('/api/v1/vendors'),
  });
}
