import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function AuditTrailPage({ params }: { params: { id: string } }) {
  const { id } = params;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href={`/invoices/${id}`}>
          <Button variant="outline" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Audit Trail</h2>
          <p className="text-muted-foreground">
            Complete history for Invoice {id}
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Event Log</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground text-center py-10 border-dashed border rounded-md">
            Audit logs placeholder...
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
