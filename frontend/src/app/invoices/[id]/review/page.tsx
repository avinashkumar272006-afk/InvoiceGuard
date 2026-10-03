import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";

export default function ReviewPage({ params }: { params: { id: string } }) {
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
            <h2 className="text-2xl font-bold tracking-tight">Human Review</h2>
            <Badge variant="destructive">Requires Action</Badge>
          </div>
          <p className="text-muted-foreground">
            Invoice {id}
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Exceptions requiring manual review</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground text-center py-10 border-dashed border rounded-md">
            Exception list and resolution form placeholder...
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
