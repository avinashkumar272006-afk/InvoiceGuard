import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

export default function PurchaseOrdersPage() {
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
          <div className="text-sm text-muted-foreground text-center py-20 border-b">
            No purchase orders found.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
