'use client';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useInvoices } from "@/hooks/use-invoices";
import { useExceptionSummary } from "@/hooks/use-exception-summary";
import { FileText, AlertCircle, CheckCircle2, Clock, XCircle, Loader2, ArrowRight } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import type { InvoiceStatus } from "@/types";

export default function DashboardPage() {
  const { data: invoices, isLoading: isLoadingInvoices, isError: isErrorInvoices } = useInvoices();
  const { data: exceptionSummary, isLoading: isLoadingExceptions, isError: isErrorExceptions } = useExceptionSummary();

  if (isLoadingInvoices || isLoadingExceptions) {
    return (
      <div className="flex items-center justify-center h-[50vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isErrorInvoices || isErrorExceptions) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center bg-background rounded-lg border">
        <AlertCircle className="h-10 w-10 text-destructive mb-4" />
        <h3 className="text-lg font-medium">Unable to load dashboard data</h3>
        <p className="text-sm text-muted-foreground mb-4">
          There was a problem connecting to the server.
        </p>
      </div>
    );
  }

  const totalInvoices = invoices?.length || 0;
  const pendingCount = invoices?.filter(i => i.status === 'PENDING').length || 0;
  const verifiedCount = invoices?.filter(i => i.status === 'VERIFIED').length || 0;
  const disputedCount = invoices?.filter(i => i.status === 'DISPUTED').length || 0;
  const paidCount = invoices?.filter(i => i.status === 'PAID').length || 0;

  // Recent invoices (sort by ID descending)
  const recentInvoices = invoices ? [...invoices].sort((a, b) => b.id - a.id).slice(0, 5) : [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground">
          Overview of invoice operations and verification status.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Invoices</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalInvoices}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{pendingCount}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Verified</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{verifiedCount}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Disputed</CardTitle>
            <XCircle className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{disputedCount}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="col-span-1 lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent Invoices</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentInvoices.length === 0 ? (
                <div className="text-sm text-muted-foreground">No recent invoices found.</div>
              ) : (
                recentInvoices.map((inv) => (
                  <div key={inv.id} className="flex items-center justify-between border-b pb-4 last:border-0 last:pb-0">
                    <div className="space-y-1">
                      <p className="text-sm font-medium leading-none">{inv.invoice_number}</p>
                      <p className="text-sm text-muted-foreground">
                        Date: {inv.issue_date} • Vendor: {inv.vendor_id} • PO: {inv.po_id || '-'}
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="font-medium tabular-nums text-right">
                        ${inv.total_amount}
                      </div>
                      <StatusBadge status={inv.status} />
                      <Link href={`/invoices/${inv.id}`} className="text-muted-foreground hover:text-foreground">
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Exception Monitoring</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">Unresolved Exceptions</div>
                  <Badge variant="outline" className="text-xs text-destructive">{exceptionSummary?.unresolved || 0}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">Resolved Exceptions</div>
                  <Badge variant="outline" className="text-xs text-emerald-600">{exceptionSummary?.resolved || 0}</Badge>
                </div>
                {exceptionSummary?.by_type && Object.keys(exceptionSummary.by_type).length > 0 && (
                  <div className="mt-4 border-t pt-4">
                    <div className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wider">Breakdown</div>
                    <div className="space-y-2">
                      {Object.entries(exceptionSummary.by_type).map(([type, count]) => (
                        <div key={type} className="flex items-center justify-between text-xs">
                          <span>{type.replace(/_/g, ' ')}</span>
                          <span className="text-muted-foreground">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Status Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <DistributionBar label="Pending" count={pendingCount} total={totalInvoices} color="bg-blue-500" />
                <DistributionBar label="Verified" count={verifiedCount} total={totalInvoices} color="bg-emerald-500" />
                <DistributionBar label="Disputed" count={disputedCount} total={totalInvoices} color="bg-red-500" />
                <DistributionBar label="Paid" count={paidCount} total={totalInvoices} color="bg-gray-500" />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function DistributionBar({ label, count, total, color }: { label: string, count: number, total: number, color: string }) {
  const percentage = total === 0 ? 0 : Math.round((count / total) * 100);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span>{label}</span>
        <span className="text-muted-foreground">{count} ({percentage}%)</span>
      </div>
      <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

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
