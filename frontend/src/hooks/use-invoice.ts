import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import type { Invoice, Verification, ExceptionResolveCreate, ExceptionResolveResponse, ReviewCreate } from '@/types';

export function useInvoice(id: string) {
  return useQuery({
    queryKey: ['invoice', id],
    queryFn: () => api.get<Invoice>(`/api/v1/invoices/${id}`),
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) return false;
      return failureCount < 1;
    }
  });
}

export function useInvoiceVerification(id: string) {
  return useQuery({
    queryKey: ['invoice-verification', id],
    queryFn: () => api.get<Verification>(`/api/v1/invoices/${id}/verification`),
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) return false;
      return failureCount < 1;
    }
  });
}

export function useVerifyInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string | number) => 
      api.post<Verification>(`/api/v1/invoices/${id}/verify`),
    onSuccess: (data, id) => {
      queryClient.invalidateQueries({ queryKey: ['invoice', String(id)] });
      queryClient.invalidateQueries({ queryKey: ['invoice-verification', String(id)] });
      queryClient.invalidateQueries({ queryKey: ['invoice-audit-logs', String(id)] });
    },
  });
}

export function useResolveException() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ invoiceId, exceptionId, data }: { invoiceId: string | number; exceptionId: number; data: ExceptionResolveCreate }) =>
      api.post<ExceptionResolveResponse>(`/api/v1/invoices/${invoiceId}/exceptions/${exceptionId}/resolve`, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['invoice', String(variables.invoiceId)] });
      queryClient.invalidateQueries({ queryKey: ['invoice-verification', String(variables.invoiceId)] });
      queryClient.invalidateQueries({ queryKey: ['invoice-audit-logs', String(variables.invoiceId)] });
    },
  });
}

export function useReviewInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ invoiceId, data }: { invoiceId: string | number; data: ReviewCreate }) =>
      api.post<Invoice>(`/api/v1/invoices/${invoiceId}/review`, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['invoice', String(variables.invoiceId)] });
      queryClient.invalidateQueries({ queryKey: ['invoice-verification', String(variables.invoiceId)] });
      queryClient.invalidateQueries({ queryKey: ['invoice-audit-logs', String(variables.invoiceId)] });
    },
  });
}
