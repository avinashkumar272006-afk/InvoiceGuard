export function Header() {
  const env = process.env.NEXT_PUBLIC_APP_ENV || 'production';
  
  return (
    <header className="h-16 border-b flex items-center justify-between px-6 bg-background">
      <div className="flex items-center gap-4">
        {env !== 'production' && (
          <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20">
            {env}
          </span>
        )}
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-sm font-medium text-muted-foreground border">
            U
          </div>
          <span className="text-sm font-medium">User (Placeholder)</span>
        </div>
      </div>
    </header>
  );
}
