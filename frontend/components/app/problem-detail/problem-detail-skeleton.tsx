import { Skeleton } from "@/components/ui/skeleton";

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
      <div className="mb-8 shrink-0 flex flex-col gap-3 lg:mb-5">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-7 w-3/4 rounded-lg" />
          <Skeleton className="h-7 w-1/2 rounded-lg" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-5 w-20 rounded-full" />
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-5 w-12" />
        </div>
        <div className="flex gap-1.5">
          <Skeleton className="h-5 w-14 rounded-full" />
          <Skeleton className="h-5 w-20 rounded-full" />
        </div>
      </div>

      {/* Two-column skeleton */}
      <div className="mt-0 grid min-h-0 flex-1 grid-cols-1 gap-0 overflow-hidden lg:grid-cols-[1fr_380px] lg:gap-10 xl:grid-cols-[1fr_420px]">
        {/* Left: book skeleton */}
        <div className="min-w-0 flex flex-col gap-5 lg:min-h-0 lg:overflow-y-auto lg:pr-2">
          <Skeleton className="h-3 w-16" />
          <div className="flex flex-col gap-3">
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-5/6" />
            <Skeleton className="h-5 w-4/5" />
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-3/4" />
          </div>
          <div className="flex flex-col gap-2 pt-2">
            <Skeleton className="h-3 w-12" />
            <div className="flex flex-col gap-2">
              {[0, 1, 2].map((i) => (
                <Skeleton
                  key={i}
                  className="h-4"
                  style={{ width: `${75 + i * 8}%` }}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Right: chain skeleton */}
        <div className="mt-10 flex flex-col gap-4 lg:mt-0 lg:min-h-0 lg:overflow-y-auto">
          <Skeleton className="h-3 w-28" />
          <div className="flex flex-col gap-4">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="w-full rounded-lg border border-border/50 px-3 py-2 flex flex-col gap-1.5"
              >
                <Skeleton
                  className="h-3"
                  style={{ width: `${50 + i * 12}%` }}
                />
                {i % 2 === 0 && <Skeleton className="h-3 w-2/3" />}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
