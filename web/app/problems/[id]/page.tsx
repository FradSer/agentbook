"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, getProblemTimeline } from "@/lib/api";
import { ProblemTimeline } from "@/lib/types";
import { ProblemDetailSkeleton } from "./problem-detail-skeleton";
import { ProblemHeader } from "./problem-header";
import { BookView } from "./book-view";
import { UpdateChain } from "./update-chain";

export default function ProblemDetailPage() {
  const params = useParams();
  const problemId = params?.id as string;
  const [data, setData] = useState<ProblemTimeline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!problemId) return;
    getProblemTimeline(problemId)
      .then(setData)
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
        else if (err instanceof Error) setError(err.message);
        else setError("Failed to load problem");
      })
      .finally(() => setLoading(false));
  }, [problemId]);

  if (loading) return <ProblemDetailSkeleton />;
  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!data) return null;

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-400 ease-out px-[20px]">
      {/* Problem header — full width */}
      <div className="mb-8">
        <ProblemHeader problem={data.problem} />
      </div>

      {/* Two-column layout on lg+, stacked on smaller screens */}
      <div className="lg:grid lg:grid-cols-[1fr_380px] lg:gap-10 xl:grid-cols-[1fr_420px]">
        {/* Left: book */}
        <div className="min-w-0">
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-5">
            Solution
          </h2>
          <BookView timeline={data.timeline} />
        </div>

        {/* Right: research chain */}
        <div className="mt-10 lg:mt-0">
          <div className="lg:sticky lg:top-6">
            <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-5">
              Research chain · {data.timeline.length} events
            </h2>
            <UpdateChain timeline={data.timeline} />
          </div>
        </div>
      </div>
    </div>
  );
}
