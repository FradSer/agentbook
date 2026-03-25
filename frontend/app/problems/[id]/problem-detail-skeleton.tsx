export function ProblemDetailSkeleton() {
  return (
    <div
      className={
        "animate-in fade-in duration-300 px-[20px] lg:flex lg:min-h-0 lg:flex-col lg:overflow-hidden " +
        "lg:h-[calc(100dvh-var(--problem-detail-layout-offset)-var(--problem-detail-layout-subpx))] " +
        "lg:max-h-[calc(100dvh-var(--problem-detail-layout-offset)-var(--problem-detail-layout-subpx))]"
      }
    >
      {/* Header */}
      <div className="mb-8 shrink-0 space-y-3 lg:mb-5">
        <div className="space-y-2">
          <div className="h-7 w-3/4 rounded-lg skeleton-pulse" />
          <div className="h-7 w-1/2 rounded-lg skeleton-pulse" />
        </div>
        <div className="flex gap-2">
          <div className="h-5 w-20 rounded-full skeleton-pulse" />
          <div className="h-5 w-16 rounded-full skeleton-pulse" />
          <div className="h-5 w-12 rounded skeleton-pulse" />
        </div>
        <div className="flex gap-1.5">
          <div className="h-5 w-14 rounded-full skeleton-pulse" />
          <div className="h-5 w-20 rounded-full skeleton-pulse" />
        </div>
      </div>

      {/* Two-column skeleton */}
      <div className="mt-0 grid min-h-0 flex-1 grid-cols-1 gap-0 overflow-hidden lg:grid-cols-[1fr_380px] lg:gap-10 xl:grid-cols-[1fr_420px]">
        {/* Left: book skeleton */}
        <div className="min-w-0 space-y-5 lg:min-h-0 lg:overflow-y-auto lg:pr-2">
          <div className="h-3 w-16 rounded skeleton-pulse" />
          <div className="space-y-3">
            <div className="h-5 w-full rounded skeleton-pulse" />
            <div className="h-5 w-5/6 rounded skeleton-pulse" />
            <div className="h-5 w-4/5 rounded skeleton-pulse" />
            <div className="h-5 w-full rounded skeleton-pulse" />
            <div className="h-5 w-3/4 rounded skeleton-pulse" />
          </div>
          <div className="space-y-2 pt-2">
            <div className="h-3 w-12 rounded skeleton-pulse" />
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-4 rounded skeleton-pulse" style={{ width: `${75 + i * 8}%` }} />
              ))}
            </div>
          </div>
        </div>

        {/* Right: chain skeleton */}
        <div className="mt-10 space-y-4 lg:mt-0 lg:min-h-0 lg:overflow-y-auto">
          <div className="h-3 w-28 rounded skeleton-pulse" />
          <div className="space-y-4">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="w-full rounded-lg border border-border/50 px-3 py-2 space-y-1.5"
              >
                <div className="h-3 rounded skeleton-pulse" style={{ width: `${50 + i * 12}%` }} />
                {i % 2 === 0 && <div className="h-3 w-2/3 rounded skeleton-pulse" />}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
