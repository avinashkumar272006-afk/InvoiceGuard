'use client';

import { use, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, AlertCircle, RefreshCw, FileText, CheckCircle2, XCircle } from "lucide-react";
import Link from "next/link";
import { 
  useInvoice, 
  useInvoiceVerification, 
  useVerifyInvoice, 
  useResolveException, 
  useReviewInvoice,
  useLinkPurchaseOrder
} from "@/hooks/use-invoice";
import { usePurchaseOrders } from "@/hooks/use-purchase-orders";
import { useDocumentUrl } from "@/hooks/use-document-url";
import { useAuditLogs } from "@/hooks/use-audit-logs";
import { ApiError } from "@/lib/api";
import { Loader2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { InvoiceStatus, VerificationStatus } from "@/types";

function InvoiceStatusBadge({ status }: { status: InvoiceStatus }) {
  switch (status) {
    case 'PENDING':
      return <Badge variant="outline">Pending</Badge>;
    case 'VERIFIED':
      return <Badge variant="default" className="bg-emerald-600 hover:bg-emerald-700">Verified</Badge>;
    case 'DISPUTED':
      return <Badge variant="destructive">Disputed</Badge>;
    case 'PAID':
      return <Badge variant="secondary">Paid</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function VerificationStatusBadge({ status }: { status: VerificationStatus }) {
  switch (status) {
    case 'PENDING':
      return <Badge variant="outline">Pending</Badge>;
    case 'PASSED':
      return <Badge variant="default" className="bg-emerald-600 hover:bg-emerald-700">Passed</Badge>;
    case 'FAILED':
      return <Badge variant="destructive">Failed</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function DocumentViewer({ documentId }: { documentId: string | null }) {
  const { data, isLoading, error, refetch, isRefetching } = useDocumentUrl(documentId);

  if (!documentId) {
    return (
      <div className="text-sm text-muted-foreground py-16 text-center border-dashed border rounded-md bg-muted/20">
        No source document is attached to this invoice.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 border border-dashed rounded-md bg-muted/10">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-4" />
        <p className="text-sm text-muted-foreground">Loading secure document link...</p>
      </div>
    );
  }

  if (error || !data?.url) {
    return (
      <div className="flex flex-col items-center justify-center py-12 border border-dashed rounded-md bg-destructive/5 text-center px-4">
        <AlertCircle className="h-8 w-8 text-destructive mb-3" />
        <p className="text-sm font-medium text-destructive mb-1">Unable to load document.</p>
        <p className="text-xs text-muted-foreground mb-4">The secure link could not be generated.</p>
        <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isRefetching}>
          <RefreshCw className={`mr-2 h-4 w-4 ${isRefetching ? 'animate-spin' : ''}`} />
          Retry
        </Button>
      </div>
    );
  }
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between bg-muted/50 p-2 rounded-md">
        <span className="text-xs text-muted-foreground font-medium ml-2">Secure link expires in 60s</span>
        <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isRefetching} className="h-8">
          <RefreshCw className={`mr-2 h-3 w-3 ${isRefetching ? 'animate-spin' : ''}`} />
          Refresh Link
        </Button>
      </div>
      
      <div className="rounded-md border bg-muted/5 overflow-hidden aspect-[3/4] relative">
        <object 
          data={data.url} 
          className="w-full h-full absolute inset-0"
          title="Document Preview"
        >
          <div className="flex flex-col items-center justify-center h-full p-6 text-center">
            <FileText className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-sm font-medium mb-2">Preview unavailable</p>
            <p className="text-xs text-muted-foreground mb-4">
              Your browser does not support embedding this document type.
            </p>
            <Button variant="outline" onClick={() => window.open(data.url, '_blank', 'noreferrer,noopener')}>
              Open document securely
            </Button>
          </div>
        </object>
      </div>
    </div>
  );
}

export default function InvoiceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  
  const { 
    data: invoice, 
    isLoading: isInvoiceLoading, 
    error: invoiceError, 
    refetch: refetchInvoice 
  } = useInvoice(id);

  const {
    data: verification,
    isLoading: isVerificationLoading,
    error: verificationError
  } = useInvoiceVerification(id);

  const { data: auditLogs, isLoading: isAuditLoading } = useAuditLogs(id);
  
  const verifyMutation = useVerifyInvoice();
  const resolveMutation = useResolveException();
  const reviewMutation = useReviewInvoice();

  const isLoading = isInvoiceLoading || isVerificationLoading;
  const is404 = invoiceError instanceof ApiError && invoiceError.status === 404;
  const isGeneralError = !!invoiceError && !is404;

  const [resolveActor, setResolveActor] = useState("");
  const [resolveComment, setResolveComment] = useState("");
  const [reviewActor, setReviewActor] = useState("");
  const [reviewComment, setReviewComment] = useState("");
  const [activeExceptionId, setActiveExceptionId] = useState<number | null>(null);

  const { data: purchaseOrders, isLoading: isPOLoading } = usePurchaseOrders();
  const linkPOMutation = useLinkPurchaseOrder();
  
  const [linkPOId, setLinkPOId] = useState<string>("");
  const [linkActor, setLinkActor] = useState("");
  const [linkComment, setLinkComment] = useState("");
  const [isLinkDialogOpen, setIsLinkDialogOpen] = useState(false);

  if (is404) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center space-y-4">
        <FileText className="h-12 w-12 text-muted-foreground" />
        <h2 className="text-2xl font-bold tracking-tight">Invoice Not Found</h2>
        <p className="text-muted-foreground max-w-sm">
          The invoice you are looking for does not exist or you don&apos;t have permission to view it.
        </p>
        <Link href="/invoices">
          <Button variant="outline">Back to Invoices</Button>
        </Link>
      </div>
    );
  }

  if (isGeneralError) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center space-y-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <h2 className="text-2xl font-bold tracking-tight">Failed to load invoice</h2>
        <p className="text-muted-foreground max-w-sm">
          There was an error communicating with the server.
        </p>
        <div className="flex gap-4 mt-4">
          <Link href="/invoices">
            <Button variant="outline">Back to Invoices</Button>
          </Link>
          <Button onClick={() => refetchInvoice()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const handleVerify = () => {
    verifyMutation.mutate(id);
  };

  const handleResolve = (exceptionId: number) => {
    if (!resolveActor.trim()) return;
    resolveMutation.mutate({
      invoiceId: id,
      exceptionId,
      data: { actor: resolveActor, comment: resolveComment || null }
    }, {
      onSuccess: () => {
        setResolveActor("");
        setResolveComment("");
        setActiveExceptionId(null);
      }
    });
  };

  const handleReview = (status: "VERIFIED" | "DISPUTED") => {
    if (!reviewActor.trim()) return;
    reviewMutation.mutate({
      invoiceId: id,
      data: { status, actor: reviewActor, comment: reviewComment || null }
    }, {
      onSuccess: () => {
        setReviewActor("");
        setReviewComment("");
      }
    });
  };

  const handleLinkPO = () => {
    if (!linkPOId || !linkActor.trim()) return;
    linkPOMutation.mutate({
      invoiceId: id,
      data: {
        po_id: parseInt(linkPOId, 10),
        actor: linkActor,
        comment: linkComment || null
      }
    }, {
      onSuccess: () => {
        setLinkPOId("");
        setLinkActor("");
        setLinkComment("");
        setIsLinkDialogOpen(false);
      }
    });
  };

  const isVerification404 = verificationError instanceof ApiError && verificationError.status === 404;

  return (
    <div className="space-y-6">
      {/* Header section */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/invoices">
            <Button variant="outline" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold tracking-tight">
                {isLoading ? (
                  <div className="h-8 w-40 bg-muted/50 rounded animate-pulse" />
                ) : (
                  `Invoice ${invoice?.invoice_number}`
                )}
              </h2>
              {!isLoading && invoice && <InvoiceStatusBadge status={invoice.status} />}
            </div>
            <p className="text-muted-foreground">
              Internal ID: {id}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Summary Card */}
          <Card>
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-4">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-6 bg-muted/50 rounded animate-pulse" />
                  ))}
                </div>
              ) : invoice ? (
                <div className="grid grid-cols-2 gap-y-4 gap-x-8 text-sm">
                  <div>
                    <p className="text-muted-foreground mb-1">Invoice Number</p>
                    <p className="font-medium">{invoice.invoice_number}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground mb-1">Issue Date</p>
                    <p className="font-medium">{invoice.issue_date}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground mb-1">Vendor ID</p>
                    <p className="font-medium">{invoice.vendor_id}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground mb-1">PO ID</p>
                    <p className="font-medium">{invoice.po_id || '-'}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground mb-1">Total Amount</p>
                    <p className="font-medium tabular-nums">{invoice.total_amount}</p>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          {/* Purchase Order Linking */}
          <Card>
            <CardHeader>
              <CardTitle>Purchase Order</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isLoading || isPOLoading ? (
                <div className="h-20 bg-muted/50 rounded animate-pulse" />
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">Currently Linked PO</p>
                      <p className="text-sm text-muted-foreground">
                        {invoice?.po_id ? `PO ID: ${invoice.po_id}` : "No purchase order linked."}
                      </p>
                    </div>
                  </div>
                  <div className="grid gap-4 bg-muted/10 p-4 border rounded-md">
                    <div>
                      <label className="text-sm font-medium mb-1 block">Select Purchase Order</label>
                      <select 
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        value={linkPOId}
                        onChange={(e) => setLinkPOId(e.target.value)}
                        disabled={linkPOMutation.isPending}
                      >
                        <option value="">Select a PO...</option>
                        {purchaseOrders?.map(po => (
                          <option key={po.id} value={po.id}>PO #{po.po_number} (Vendor {po.vendor_id})</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-sm font-medium mb-1 block">Reviewer Name <span className="text-destructive">*</span></label>
                      <Input 
                        placeholder="Enter your name" 
                        value={linkActor} 
                        onChange={(e) => setLinkActor(e.target.value)}
                        disabled={linkPOMutation.isPending}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium mb-1 block">Reason for linking this PO (Optional)</label>
                      <Input 
                        placeholder="Review comment" 
                        value={linkComment} 
                        onChange={(e) => setLinkComment(e.target.value)}
                        disabled={linkPOMutation.isPending}
                      />
                    </div>
                    
                    <Dialog open={isLinkDialogOpen} onOpenChange={setIsLinkDialogOpen}>
                      <DialogTrigger render={
                        <Button 
                          className="w-full"
                          disabled={!linkPOId || !linkActor.trim() || linkPOMutation.isPending}
                        />
                      }>
                        {invoice?.po_id ? "Relink Purchase Order..." : "Link Purchase Order..."}
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Confirm Purchase Order Link</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                          <p className="text-sm">Are you sure you want to link this Purchase Order to the invoice? This will automatically rerun verification.</p>
                          <div className="text-sm bg-muted p-3 rounded-md space-y-2">
                            <p><strong>Invoice:</strong> {invoice?.invoice_number} (ID: {invoice?.id})</p>
                            <p><strong>Selected PO ID:</strong> {linkPOId}</p>
                            <p><strong>Actor:</strong> {linkActor}</p>
                            <p><strong>Comment:</strong> {linkComment || "None"}</p>
                          </div>
                          {linkPOMutation.isError && (
                            <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                              {linkPOMutation.error instanceof ApiError ? (linkPOMutation.error.data as Record<string, unknown>)?.detail as string || "Failed to link PO." : "An error occurred."}
                            </div>
                          )}
                          <div className="flex justify-end gap-3 mt-4">
                            <Button variant="outline" disabled={linkPOMutation.isPending} onClick={() => setIsLinkDialogOpen(false)}>
                              Cancel
                            </Button>
                            <Button onClick={handleLinkPO} disabled={linkPOMutation.isPending}>
                              {linkPOMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                              Confirm / Link PO
                            </Button>
                          </div>
                        </div>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Items Table */}
          <Card>
            <CardHeader>
              <CardTitle>Invoice Items</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-4">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-10 bg-muted/50 rounded animate-pulse" />
                  ))}
                </div>
              ) : invoice?.items && invoice.items.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Description</TableHead>
                        <TableHead className="text-right">Qty</TableHead>
                        <TableHead className="text-right">Unit Price</TableHead>
                        <TableHead className="text-right">Total Price</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {invoice.items.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell className="font-medium">{item.description}</TableCell>
                          <TableCell className="text-right tabular-nums">{item.quantity}</TableCell>
                          <TableCell className="text-right tabular-nums">{item.unit_price}</TableCell>
                          <TableCell className="text-right tabular-nums">{item.total_price}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-6 text-sm text-muted-foreground border border-dashed rounded-md">
                  No items listed for this invoice.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Human Review Panel */}
          {invoice?.status === 'PENDING' && (
            <Card>
              <CardHeader>
                <CardTitle>Human Review</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4">
                  <div>
                    <label className="text-sm font-medium mb-1 block">Reviewer Name <span className="text-destructive">*</span></label>
                    <Input 
                      placeholder="Enter your name" 
                      value={reviewActor} 
                      onChange={(e) => setReviewActor(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-1 block">Comment (Optional)</label>
                    <Input 
                      placeholder="Add a comment" 
                      value={reviewComment} 
                      onChange={(e) => setReviewComment(e.target.value)}
                    />
                  </div>
                </div>
                
                {reviewMutation.isError && (
                  <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-md">
                    {reviewMutation.error instanceof ApiError ? (reviewMutation.error.data as Record<string, unknown>)?.detail as string || "Review failed." : "An error occurred."}
                  </div>
                )}
                
                <div className="flex gap-4">
                  <Button 
                    className="flex-1 bg-emerald-600 hover:bg-emerald-700" 
                    onClick={() => handleReview("VERIFIED")}
                    disabled={!reviewActor.trim() || reviewMutation.isPending}
                  >
                    {reviewMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                    Approve / Mark Verified
                  </Button>
                  <Button 
                    variant="destructive" 
                    className="flex-1"
                    onClick={() => handleReview("DISPUTED")}
                    disabled={!reviewActor.trim() || reviewMutation.isPending}
                  >
                    {reviewMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <XCircle className="mr-2 h-4 w-4" />}
                    Mark Disputed
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  All exceptions must be resolved before this invoice can be verified.
                </p>
              </CardContent>
            </Card>
          )}

          {/* Audit Trail Panel */}
          <Card>
            <CardHeader>
              <CardTitle>Audit Trail</CardTitle>
            </CardHeader>
            <CardContent>
              {isAuditLoading ? (
                <div className="h-20 bg-muted/50 rounded animate-pulse" />
              ) : auditLogs && auditLogs.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Time</TableHead>
                        <TableHead>Actor</TableHead>
                        <TableHead>Action</TableHead>
                        <TableHead>Details</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {auditLogs.map((log) => (
                        <TableRow key={log.id}>
                          <TableCell className="text-xs whitespace-nowrap">
                            {new Date(log.created_at).toLocaleString()}
                          </TableCell>
                          <TableCell className="font-medium text-sm">{log.actor}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-xs">{log.action}</Badge>
                          </TableCell>
                          <TableCell className="text-sm">
                            <span className="font-medium">{log.entity_name}</span>
                            {log.previous_state && log.new_state && (
                              <span className="text-muted-foreground ml-2">
                                {log.previous_state} → {log.new_state}
                              </span>
                            )}
                            {log.comment && (
                              <p className="text-muted-foreground text-xs mt-1 italic">
                                &quot;{log.comment}&quot;
                              </p>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-6 text-sm text-muted-foreground border border-dashed rounded-md">
                  No audit logs found.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          {/* Verification Overview */}
          <Card>
            <CardHeader>
              <CardTitle>Verification Overview</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-4">
                  <div className="h-6 bg-muted/50 rounded animate-pulse" />
                  <div className="h-6 bg-muted/50 rounded animate-pulse" />
                </div>
              ) : isVerification404 ? (
                <div className="space-y-4">
                  <div className="text-sm text-muted-foreground text-center py-4 border border-dashed rounded-md mb-4">
                    Verification has not run yet.
                  </div>
                  <Button 
                    className="w-full" 
                    onClick={handleVerify}
                    disabled={verifyMutation.isPending}
                  >
                    {verifyMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircle2 className="mr-2 h-4 w-4" />
                    )}
                    Run Verification
                  </Button>
                  {verifyMutation.isError && (
                    <p className="text-xs text-destructive text-center mt-2">
                      {verifyMutation.error instanceof ApiError ? (verifyMutation.error.data as Record<string, unknown>)?.detail as string || "Verification failed" : "An error occurred"}
                    </p>
                  )}
                </div>
              ) : verification ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Status</span>
                    <VerificationStatusBadge status={verification.status} />
                  </div>
                  {verification.verified_at && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Verified At</span>
                      <span className="text-sm font-medium">{new Date(verification.verified_at).toLocaleString()}</span>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Exceptions</span>
                    <Badge variant="outline">{verification.exceptions?.length || 0}</Badge>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  Verification data unavailable.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Exceptions Panel */}
          {verification?.exceptions && verification.exceptions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Exceptions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {verification.exceptions.map((exc) => (
                  <div key={exc.id} className={`p-3 rounded-md border ${exc.resolved ? 'bg-muted/30 border-muted' : 'bg-destructive/10 border-destructive/20 text-destructive'}`}>
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-semibold text-sm">{exc.exception_type}</span>
                      {exc.resolved ? (
                        <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-200">Resolved</Badge>
                      ) : (
                        <Badge variant="destructive">Unresolved</Badge>
                      )}
                    </div>
                    <p className={`text-sm mb-3 ${exc.resolved ? 'text-muted-foreground' : ''}`}>{exc.description}</p>
                    
                    {!exc.resolved && (
                      <Dialog open={activeExceptionId === exc.id} onOpenChange={(isOpen) => isOpen ? setActiveExceptionId(exc.id) : setActiveExceptionId(null)}>
                        <DialogTrigger render={<Button size="sm" variant="outline" className="w-full" />}>
                          Resolve
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Resolve Exception</DialogTitle>
                          </DialogHeader>
                          <div className="space-y-4 py-4">
                            <div>
                              <label className="text-sm font-medium mb-1 block">Reviewer Name <span className="text-destructive">*</span></label>
                              <Input 
                                placeholder="Enter your name" 
                                value={resolveActor} 
                                onChange={(e) => setResolveActor(e.target.value)}
                              />
                            </div>
                            <div>
                              <label className="text-sm font-medium mb-1 block">Comment (Optional)</label>
                              <Input 
                                placeholder="Add a resolution comment" 
                                value={resolveComment} 
                                onChange={(e) => setResolveComment(e.target.value)}
                              />
                            </div>
                            {resolveMutation.isError && (
                              <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-md">
                                {resolveMutation.error instanceof ApiError ? (resolveMutation.error.data as Record<string, unknown>)?.detail as string || "Resolution failed" : "An error occurred"}
                              </div>
                            )}
                            <Button 
                              className="w-full" 
                              onClick={() => handleResolve(exc.id)}
                              disabled={!resolveActor.trim() || resolveMutation.isPending}
                            >
                              {resolveMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                              Submit Resolution
                            </Button>
                          </div>
                        </DialogContent>
                      </Dialog>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Document Viewer */}
          <Card>
            <CardHeader>
              <CardTitle>Source Document</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="h-64 bg-muted/50 rounded animate-pulse" />
              ) : (
                <DocumentViewer documentId={invoice?.document_id || null} />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
