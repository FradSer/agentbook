export function ProblemDetailSkeleton() {
  return (
    <div className="space-y-6 max-w-3xl mx-auto animate-in fade-in duration-300">
      <div className="space-y-3">
        <div className="space-y-2">
          <div className="h-7 w-3/4 rounded-lg skeleton-pulse" />
          <div className="h-7 w-1/2 rounded-lg skeleton-pulse" />
        </div>
        <div className="flex gap-2">
          <div className="h-5 w-28 rounded skeleton-pulse" />
          <div className="h-5 w-16 rounded-full skeleton-pulse" />
        </div>
        <div className="flex gap-1.5">
          <div className="h-5 w-14 rounded-full skeleton-pulse" />
          <div className="h-5 w-20 rounded-full skeleton-pulse" />
        </div>
      </div>
      <div className="space-y-3">
        <div className="h-6 w-40 rounded skeleton-pulse" />
        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <div className="flex gap-2">
            <div className="h-5 w-16 rounded-full skeleton-pulse" />
            <div className="h-5 w-24 rounded-full skeleton-pulse" />
          </div>
          <div className="space-y-2">
            <div className="h-4 w-full rounded skeleton-pulse" />
            <div className="h-4 w-5/6 rounded skeleton-pulse" />
            <div className="h-4 w-4/6 rounded skeleton-pulse" />
          </div>
        </div>
      </div>
      <div className="space-y-3">
        <div className="h-6 w-36 rounded skeleton-pulse" />
        {[0, 1].map((i) => (
          <div key={i} className="rounded-xl border border-border bg-card p-5 space-y-3">
            <div className="flex gap-2">
              <div className="h-5 w-12 rounded-full skeleton-pulse" />
              <div className="h-5 w-20 rounded skeleton-pulse" />
            </div>
            <div className="space-y-2">
              <div className="h-4 w-full rounded skeleton-pulse" />
              <div className="h-4 w-3/4 rounded skeleton-pulse" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
