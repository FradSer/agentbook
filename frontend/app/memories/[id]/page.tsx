"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  BookSolutionMetaBar,
  BookView,
} from "@/components/app/problem-detail/book-view";
import { ProblemDetailSkeleton } from "@/components/app/problem-detail/problem-detail-skeleton";
import { ProblemHeader } from "@/components/app/problem-detail/problem-header";
import { UpdateChain } from "@/components/app/problem-detail/update-chain";
import { Button } from "@/components/ui/button";
import { ApiError, getProblemTimeline } from "@/lib/api";
import type { ProblemTimeline } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function ProblemDetailPage() {
  const params = useParams();
  const problemId = params?.id as string;
  const [data, setData] = useState<ProblemTimeline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadTimeline = useCallback(async () => {
    if (!problemId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await getProblemTimeline(problemId);
      setData(result);
    } catch (err: unknown) {
      if (err instanceof ApiError) setError(err.message);
      else if (err instanceof Error) setError(err.message);
      else setError("Failed to load problem");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [problemId]);

  useEffect(() => {
    if (!problemId) return;
    setData(null);
    loadTimeline();
  }, [problemId, loadTimeline]);

  if (loading) return <ProblemDetailSkeleton />;
  if (error) {
    return (
      <div className="px-[20px]">
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 py-12 text-center">
          <p className="font-medium text-destructive">Failed to load problem</p>
          <p className="mt-1 text-sm text-muted-foreground">{error}</p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Button type="button" onClick={() => void loadTimeline()}>
              Retry
            </Button>
            <Button variant="outline" asChild>
              <Link href="/">Back to Library</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div
      className={cn(
        "animate-in fade-in slide-in-from-bottom-2 duration-400 ease-out px-[20px]",
        "lg:flex lg:min-h-0 lg:flex-col lg:overflow-hidden",
        "lg:h-[calc(100dvh-var(--problem-detail-layout-offset)-var(--problem-detail-layout-subpx))] lg:max-h-[calc(100dvh-var(--problem-detail-layout-offset)-var(--problem-detail-layout-subpx))]",
      )}
    >
      {/* Problem header — full width; stays above the scroll regions on lg+ */}
      <div className="mb-8 shrink-0 lg:mb-5">
        <ProblemHeader problem={data.problem} />
      </div>

      {/* Two-column layout on lg+: fills remaining viewport; each column scrolls independently. */}
      <div className="mt-0 grid min-h-0 flex-1 grid-cols-1 gap-0 overflow-hidden lg:grid-cols-[1fr_380px] lg:gap-10 xl:grid-cols-[1fr_420px]">
        {/* Left: book */}
        <div className="min-w-0 lg:flex lg:min-h-0 lg:flex-col lg:overflow-hidden">
          <div className="mb-5 flex min-w-0 shrink-0 flex-wrap items-center gap-x-4 gap-y-2">
            <h2 className="font-sans text-xs font-medium uppercase tracking-widest text-muted-foreground shrink-0">
              Solution
            </h2>
            <BookSolutionMetaBar book={data.book_solution} />
          </div>
          <div className="scroll-panel min-h-0 flex-1 lg:pr-2">
            <BookView book={data.book_solution} />
          </div>
        </div>

        {/* Right: research chain */}
        <div className="mt-10 flex min-h-0 flex-col overflow-hidden lg:mt-0">
          <h2 className="mb-5 shrink-0 font-sans text-xs font-medium uppercase tracking-widest text-muted-foreground">
            Research chain · {data.timeline.length} events
          </h2>
          <div className="scroll-panel min-h-0 flex-1">
            <UpdateChain timeline={data.timeline} />
          </div>
        </div>
      </div>
    </div>
  );
}
