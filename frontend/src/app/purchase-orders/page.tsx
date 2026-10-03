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
import { AlertCircle, RefreshCw, ShoppingCart, Plus } from "lucide-react";
import { usePurchaseOrders } from "@/hooks/use-purchase-orders";
import type { POStatus } from "@/types";

function StatusBadge({ status }: { status: POStatus }) {
  switch (status) {
    case 'PENDING':
      return <Badge variant="outline">Pending</Badge>;
    case 'APPROVED':
      return <Badge variant="default" className="bg-emerald-600 hover:bg-emerald-700">Approved</Badge>;
    case 'REJECTED':
      return <Badge variant="destructive">Rejected</Badge>;
    case 'COMPLETED':
      return <Badge variant="secondary">Completed</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export default function PurchaseOrdersPage() {
  const { data: purchaseOrders, isLoading, isError, refetch } = usePurchaseOrders();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Purchase Orders</h2>
          <p className="text-muted-foreground">
            Manage POs for invoice matching.
          </p>
        </div>
        <Button disabled>
          <Plus className="mr-2 h-4 w-4" />
          Create PO
        </Button>
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
              <h3 className="text-lg font-medium">Failed to load purchase orders</h3>
              <p className="text-sm text-muted-foreground mb-4">
                There was a problem connecting to the server.
              </p>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Retry
              </Button>
            </div>
          )}

          {!isLoading && !isError && purchaseOrders?.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4">
                <ShoppingCart className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-medium">No purchase orders found.</h3>
              <p className="text-sm text-muted-foreground max-w-sm mb-4">
                You do not have any purchase orders available in the system yet.
              </p>
            </div>
          )}

          {!isLoading && !isError && purchaseOrders && purchaseOrders.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>PO Number</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Vendor ID</TableHead>
                  <TableHead>Items</TableHead>
                  <TableHead className="text-right">Total Amount</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {purchaseOrders.map((po) => (
                  <TableRow key={po.id}>
                    <TableCell className="font-medium">{po.po_number}</TableCell>
                    <TableCell>{po.issue_date}</TableCell>
                    <TableCell>{po.vendor_id}</TableCell>
                    <TableCell>{po.items?.length || 0}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {po.total_amount}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={po.status} />
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
