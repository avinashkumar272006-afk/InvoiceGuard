'use client';

import { useState, useRef, useCallback } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, UploadCloud, File as FileIcon, X, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useDocumentUpload } from "@/hooks/use-document-upload";

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_TYPES = ['application/pdf', 'image/png', 'image/jpeg'];

export default function InvoiceUploadPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const { state, error, upload, reset } = useDocumentUpload();

  const handleFileSelect = (file: File) => {
    setValidationError(null);
    reset();

    if (!ALLOWED_TYPES.includes(file.type)) {
      setValidationError("Unsupported file type. Please upload a PDF, PNG, or JPEG.");
      setSelectedFile(null);
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setValidationError("File exceeds the 10 MB limit.");
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (state === 'UPLOADING' || state === 'PROCESSING') return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    const invoiceId = await upload(selectedFile);
    if (invoiceId) {
      // Success
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      // Short delay for UX so user can read "Completed"
      setTimeout(() => {
        router.push(`/invoices/${invoiceId}`);
      }, 1000);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / 1048576).toFixed(1) + ' MB';
  };

  const isBusy = state === 'UPLOADING' || state === 'PROCESSING' || state === 'SUCCESS';

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/invoices">
          <Button variant="outline" size="icon" disabled={isBusy}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Upload Invoice</h2>
          <p className="text-muted-foreground">
            Upload a document for AI extraction and verification.
          </p>
        </div>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Select Document</CardTitle>
          <CardDescription>Supported formats: PDF, PNG, JPG (Max 10MB).</CardDescription>
        </CardHeader>
        <CardContent>
          <div 
            className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
              isDragging ? 'border-primary bg-primary/5' : 'border-muted hover:bg-muted/50'
            } ${isBusy ? 'opacity-50 pointer-events-none' : 'cursor-pointer'}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => !isBusy && fileInputRef.current?.click()}
          >
            <input 
              type="file" 
              className="hidden" 
              ref={fileInputRef}
              accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleFileSelect(e.target.files[0]);
                }
                // Reset input value so the same file can be selected again if removed
                e.target.value = '';
              }}
            />

            {!selectedFile ? (
              <>
                <div className="mx-auto flex justify-center mb-4">
                  <UploadCloud className="h-10 w-10 text-muted-foreground" />
                </div>
                <h3 className="text-lg font-medium">Click to upload or drag and drop</h3>
                <p className="text-sm text-muted-foreground mt-2">
                  Maximum file size 10 MB
                </p>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center space-y-4">
                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                  <FileIcon className="h-6 w-6 text-primary" />
                </div>
                <div className="text-center">
                  <p className="font-medium truncate max-w-[250px] sm:max-w-xs">{selectedFile.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {formatFileSize(selectedFile.size)} • {selectedFile.type || 'Unknown type'}
                  </p>
                </div>
              </div>
            )}
          </div>
          
          {validationError && (
            <div className="mt-4 p-3 bg-destructive/10 text-destructive text-sm rounded-md flex items-start gap-2">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>{validationError}</span>
            </div>
          )}

          {state === 'ERROR' && error && (
            <div className="mt-4 p-3 bg-destructive/10 text-destructive text-sm rounded-md flex items-start gap-2">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold block mb-1">Upload or Processing failed</span>
                <span>{error}</span>
              </div>
            </div>
          )}

          {isBusy && (
            <div className="mt-6 p-4 border rounded-lg bg-muted/30">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {state === 'SUCCESS' ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  ) : (
                    <Loader2 className="h-5 w-5 text-primary animate-spin" />
                  )}
                  <div className="font-medium text-sm">
                    {state === 'UPLOADING' && "Uploading invoice..."}
                    {state === 'PROCESSING' && "Processing invoice..."}
                    {state === 'SUCCESS' && "Invoice processed successfully"}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="mt-6 flex justify-between">
            <Button 
              variant="outline" 
              onClick={(e) => {
                e.stopPropagation();
                setSelectedFile(null);
                setValidationError(null);
                reset();
              }}
              disabled={!selectedFile || isBusy}
            >
              <X className="mr-2 h-4 w-4" />
              Remove File
            </Button>
            
            <Button 
              onClick={handleUpload}
              disabled={!selectedFile || isBusy}
            >
              {isBusy ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing
                </>
              ) : (
                <>
                  <UploadCloud className="mr-2 h-4 w-4" />
                  Process Invoice
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
