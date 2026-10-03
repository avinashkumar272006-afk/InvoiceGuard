import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { DocumentUrlResponse } from '@/types';

export function useDocumentUrl(documentId: string | null) {
  return useQuery({
    queryKey: ['document-url', documentId],
    queryFn: async () => {
      if (!documentId) return null;
      return api.get<DocumentUrlResponse>(`/api/v1/documents/${documentId}/file`);
    },
    enabled: !!documentId,
    // Do not retry on 404s/403s
    retry: false,
    // Document URLs expire quickly (60s), so we shouldn't cache them for long
    // If the component unmounts and remounts, we should fetch a fresh URL to avoid using an expired one
    staleTime: 0,
    gcTime: 0, 
    refetchOnWindowFocus: false,
  });
}
