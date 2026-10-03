import { useState } from 'react';
import { api, ApiError } from '@/lib/api';
import type { DocumentResponse, DocumentProcessingResponse } from '@/types';

export type UploadState = 'IDLE' | 'UPLOADING' | 'PROCESSING' | 'SUCCESS' | 'ERROR';

export function useDocumentUpload() {
  const [state, setState] = useState<UploadState>('IDLE');
  const [error, setError] = useState<string | null>(null);

  const upload = async (file: File): Promise<number | null> => {
    setState('UPLOADING');
    setError(null);
    try {
      // 1. Upload
      const formData = new FormData();
      formData.append('file', file);
      
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
      const uploadRes = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
        method: 'POST',
        body: formData,
      });
      
      if (!uploadRes.ok) {
        let errData;
        try { errData = await uploadRes.json(); } catch(e: unknown) {}
        const detail = errData?.detail || uploadRes.statusText;
        // Sometimes FastAPI throws an array of validation errors for body/form data
        const message = Array.isArray(detail) ? JSON.stringify(detail) : detail;
        throw new ApiError(uploadRes.status, message || 'Upload failed', errData);
      }
      const uploadData: DocumentResponse = await uploadRes.json();

      // 2. Process
      setState('PROCESSING');
      const processData = await api.post<DocumentProcessingResponse>(`/api/v1/documents/${uploadData.id}/process`);
      
      setState('SUCCESS');
      return processData.invoice_id;
    } catch (err: unknown) {
      setState('ERROR');
      if (err instanceof ApiError) {
        const detail = (err.data as Record<string, unknown>)?.detail;
        const msg = Array.isArray(detail) ? JSON.stringify(detail) : detail;
        setError((msg as string) || err.message || "An error occurred");
      } else if (err instanceof Error) {
        setError(err.message || "An error occurred");
      } else {
        setError("An error occurred");
      }
      return null;
    }
  };

  const reset = () => {
    setState('IDLE');
    setError(null);
  };

  return {
    state,
    error,
    upload,
    reset,
  };
}
