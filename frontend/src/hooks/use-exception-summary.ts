import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { ExceptionSummary } from '@/types';

export function useExceptionSummary() {
  return useQuery({
    queryKey: ['exceptionSummary'],
    queryFn: () => api.get<ExceptionSummary>('/api/v1/exceptions/summary'),
  });
}
