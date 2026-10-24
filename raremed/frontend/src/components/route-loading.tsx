export function RouteLoading() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-6 py-16" aria-busy="true">
      <div className="h-4 w-28 animate-pulse rounded-full bg-muted" />
      <div className="h-10 w-2/3 animate-pulse rounded-lg bg-muted" />
      <div className="h-24 animate-pulse rounded-xl bg-muted" />
      <div className="h-24 animate-pulse rounded-xl bg-muted" />
    </div>
  );
}
