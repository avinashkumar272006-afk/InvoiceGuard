import Link from "next/link";
import { LayoutDashboard, FileText, Users, ShoppingCart } from "lucide-react";

export function Sidebar() {
  return (
    <aside className="w-64 border-r bg-muted/20 min-h-screen flex flex-col">
      <div className="p-6 border-b">
        <h1 className="text-xl font-bold tracking-tight">InvoiceGuard</h1>
        <p className="text-sm text-muted-foreground mt-1">Verification Platform</p>
      </div>
      <nav className="p-4 flex-1 space-y-1">
        <Link href="/dashboard" className="flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md hover:bg-muted text-foreground">
          <LayoutDashboard className="h-4 w-4" />
          Dashboard
        </Link>
        <Link href="/invoices" className="flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md hover:bg-muted text-foreground">
          <FileText className="h-4 w-4" />
          Invoices
        </Link>
        <Link href="/vendors" className="flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md hover:bg-muted text-foreground">
          <Users className="h-4 w-4" />
          Vendors
        </Link>
        <Link href="/purchase-orders" className="flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md hover:bg-muted text-foreground">
          <ShoppingCart className="h-4 w-4" />
          Purchase Orders
        </Link>
      </nav>
      <div className="p-4 border-t text-xs text-muted-foreground">
        Secure B2B Processing
      </div>
    </aside>
  );
}
