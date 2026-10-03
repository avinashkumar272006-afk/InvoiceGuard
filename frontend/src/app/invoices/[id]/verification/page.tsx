import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";

export default function VerificationPage({ params }: { params: { id: string } }) {
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
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold tracking-tight">System Verification</h2>
            <Badge variant="outline">Rules Engine</Badge>
          </div>
          <p className="text-muted-foreground">
            Invoice {id}
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Business Rules & PO Matching</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground text-center py-10 border-dashed border rounded-md">
            Verification steps placeholder...
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
