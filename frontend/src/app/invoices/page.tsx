'use client';

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Link from "next/link";
import { Upload, AlertCircle, RefreshCw } from "lucide-react";
import { useInvoices } from "@/hooks/use-invoices";
import type { InvoiceStatus } from "@/types";

function StatusBadge({ status }: { status: InvoiceStatus }) {
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

export default function InvoicesPage() {
  const { data: invoices, isLoading, isError, refetch } = useInvoices();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Invoices</h2>
          <p className="text-muted-foreground">
            Manage and verify your supplier invoices.
          </p>
        </div>
        <Link href="/invoices/upload">
          <Button>
            <Upload className="mr-2 h-4 w-4" />
            Upload Invoice
          </Button>
        </Link>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading && (
            <div className="p-8 space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-12 bg-muted/50 rounded-md animate-pulse" />
              ))}
            </div>
          )}

          {isError && !isLoading && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <AlertCircle className="h-10 w-10 text-destructive mb-4" />
              <h3 className="text-lg font-medium">Failed to load invoices</h3>
              <p className="text-sm text-muted-foreground mb-4">
                There was a problem connecting to the server.
              </p>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Retry
              </Button>
            </div>
          )}

          {!isLoading && !isError && invoices?.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4">
                <Upload className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-medium">No invoices yet</h3>
              <p className="text-sm text-muted-foreground max-w-sm mb-4">
                Upload your first invoice document to begin extraction and verification.
              </p>
              <Link href="/invoices/upload">
                <Button variant="outline">Upload Invoice</Button>
              </Link>
            </div>
          )}

          {!isLoading && !isError && invoices && invoices.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Invoice #</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Vendor ID</TableHead>
                  <TableHead>PO ID</TableHead>
                  <TableHead className="text-right">Total Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.map((invoice) => (
                  <TableRow key={invoice.id}>
                    <TableCell className="font-medium">{invoice.invoice_number}</TableCell>
                    <TableCell>{invoice.issue_date}</TableCell>
                    <TableCell>{invoice.vendor_id}</TableCell>
                    <TableCell>{invoice.po_id || '-'}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {invoice.total_amount}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={invoice.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Link href={`/invoices/${invoice.id}`}>
                        <Button variant="ghost" size="sm">
                          View
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
