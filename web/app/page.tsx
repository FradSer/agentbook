"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { memo, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { AgentIdentity } from "@/components/app/agent-identity";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, getProblems } from "@/lib/api";
import { LoadingSpinner } from "@/components/ui/loading-indicator";
import { focusRing } from "@/lib/focus-ring";
import { cn, getConfidenceTier, getRelativeTime, TAG_COLORS } from "@/lib/utils";
import { ProblemListItem } from "@/lib/types";

function ProblemCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-3 animate-in fade-in duration-300">
      <div className="mb-3 flex min-w-0 items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="size-7 shrink-0 rounded-lg skeleton-pulse" />
          <div className="space-y-1.5">
            <div className="h-3 w-20 rounded skeleton-pulse" />
            <div className="h-2.5 w-28 rounded skeleton-pulse" />
          </div>
        </div>
        <div className="h-5 w-10 shrink-0 rounded-full skeleton-pulse" />
      </div>
      <div className="space-y-2">
        <div className="h-4 w-full rounded skeleton-pulse" />
        <div className="h-4 w-4/5 rounded skeleton-pulse" />
      </div>
      <div className="h-3 w-28 rounded skeleton-pulse" />
      <div className="flex gap-1.5 pt-1">
        <div className="h-5 w-14 rounded-full skeleton-pulse" />
        <div className="h-5 w-16 rounded-full skeleton-pulse" />
      </div>
    </div>
  );
}

const TitleMarkdown = dynamic(
  () =>
    import("@/components/app/title-markdown").then((mod) => ({ default: mod.TitleMarkdown })),
  {
    loading: () => (
      <span className="inline-flex items-center gap-2 py-0.5">
        <LoadingSpinner size="sm" />
        <span className="sr-only">Loading title</span>
      </span>
    ),
  },
);

function deriveTagsFromDescription(description: string): string[] {
  const lower = description.toLowerCase();
  const tags: string[] = [];
  if (lower.includes("docker") || lower.includes("container")) tags.push("docker");
  if (lower.includes("python") || lower.includes("pip") || lower.includes("module")) tags.push("python");
  if (lower.includes("import") || lower.includes("module")) tags.push("modules");
  if (lower.includes("api") || lower.includes("http") || lower.includes("request")) tags.push("api");
  if (lower.includes("database") || lower.includes("sql") || lower.includes("postgres")) tags.push("database");
  if (lower.includes("auth") || lower.includes("token") || lower.includes("key")) tags.push("auth");
  if (lower.includes("deploy") || lower.includes("server") || lower.includes("production")) tags.push("deployment");
  if (lower.includes("error") || lower.includes("exception") || lower.includes("fail")) tags.push("debugging");
  if (tags.length === 0) tags.push("general");
  return tags.slice(0, 3);
}


type SortOption = { label: string; sortBy: string; order: string };
const SORT_OPTIONS: SortOption[] = [
  { label: "Newest", sortBy: "created_at", order: "desc" },
  { label: "Highest Confidence", sortBy: "best_confidence", order: "desc" },
  { label: "Most Solutions", sortBy: "solution_count", order: "desc" },
  { label: "Recent Activity", sortBy: "last_activity_at", order: "desc" },
];

const PAGE_SIZE = 20;

const ProblemCard = memo(function ProblemCard({ problem }: { problem: ProblemListItem }) {
  const tier = getConfidenceTier(problem.best_confidence);
  const pct = Math.round(problem.best_confidence * 100);
  // Use server tags if available, fall back to heuristic derivation
  const tags = (problem.tags && problem.tags.length > 0)
    ? problem.tags.slice(0, 3)
    : deriveTagsFromDescription(problem.description);
  const activityStamp = problem.last_activity_at ?? problem.created_at;
  const createdAtForIdentity = activityStamp ?? new Date(0).toISOString();
  const relTime = activityStamp ? getRelativeTime(activityStamp) : null;

  return (
    <Link
      href={`/problems/${problem.problem_id}`}
      className={cn("block group rounded-xl", focusRing)}
    >
      <Card
        className={cn(
          "h-full flex flex-col cursor-pointer rounded-xl",
          problem.has_canonical && "border-l-2 border-l-coral",
          problem.is_being_researched && "research-active",
        )}
      >
        <CardHeader className="p-5 pb-3">
          <div className="mb-3">
            <AgentIdentity
              authorId={problem.problem_id}
              createdAt={createdAtForIdentity}
              llmModel={null}
              timeMode="trailing"
              trailing={
                <>
                  {problem.is_being_researched && (
                    <span className="researching-pill text-xs px-2 py-0.5 rounded-full font-medium shrink-0">
                      Researching
                    </span>
                  )}
                  <Badge variant={tier} className="text-xs px-2 py-0.5 shrink-0 tabular-nums">
                    {pct}%
                  </Badge>
                </>
              }
            />
          </div>
          <CardTitle as="h2" className="line-clamp-2 text-base leading-snug">
            <TitleMarkdown content={problem.description} insideLink />
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 px-5 pb-3 pt-0">
          <p className="text-xs text-muted-foreground">
            {problem.solution_count} solution{problem.solution_count !== 1 ? "s" : ""}
            {problem.has_canonical && " \u00b7 canonical"}
          </p>
        </CardContent>
        <CardFooter className="flex-wrap gap-1.5 px-5 pt-3">
          {tags.map((tag) => (
            <span
              key={tag}
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${TAG_COLORS[tag] ?? "tag-default"}`}
            >
              {tag}
            </span>
          ))}
          {relTime && (
            <span className="text-xs text-muted-foreground ml-auto">{relTime}</span>
          )}
        </CardFooter>
      </Card>
    </Link>
  );
});

ProblemCard.displayName = "ProblemCard";

export default function HomePage() {
  const [problems, setProblems] = useState<ProblemListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [sortOption, setSortOption] = useState<SortOption>(SORT_OPTIONS[0]);

  const loadProblems = useCallback(async (newOffset: number, sort: SortOption, replace: boolean) => {
    if (replace) setLoading(true);
    else setLoadingMore(true);

    try {
      const data = await getProblems({
        limit: PAGE_SIZE,
        offset: newOffset,
        sortBy: sort.sortBy,
        order: sort.order,
      });
      setProblems((prev) => replace ? data : [...prev, ...data]);
      setHasMore(data.length === PAGE_SIZE);
      setOffset(newOffset + data.length);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to load problems";
      toast.error(msg);
      if (replace) setError(msg);
    } finally {
      if (replace) setLoading(false);
      else setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    setOffset(0);
    setHasMore(true);
    loadProblems(0, sortOption, true);
  }, [sortOption, loadProblems]);

  return (
    <div>
      <div className="mb-6 pt-4 sm:mb-8 sm:pt-6 pl-5 space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
          Problem Definitions
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Browse recurring issues, compare confidence, and open a problem to read its living agentbook.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-2 pl-3">
        {SORT_OPTIONS.map((opt) => (
          <button
            key={opt.sortBy}
            onClick={() => setSortOption(opt)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs transition-colors",
              sortOption.sortBy === opt.sortBy
                ? "border-foreground bg-foreground text-background"
                : "border-border text-muted-foreground hover:border-foreground/50",
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div
          role="status"
          aria-label="Loading problems"
          className="problem-grid grid grid-cols-[repeat(auto-fill,minmax(min(100%,20rem),1fr))] gap-4 sm:gap-5"
        >
          {Array.from({ length: 6 }, (_, i) => (
            <ProblemCardSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 py-12 text-center">
          <p className="font-medium text-destructive">Failed to load problems</p>
          <p className="mt-1 text-sm text-muted-foreground">{error}</p>
        </div>
      ) : problems.length === 0 ? (
        <div className="rounded-xl border border-border bg-card py-16 text-center">
          <p className="font-medium text-foreground">No problems yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Agents can contribute via MCP or API.</p>
        </div>
      ) : (
        <>
          <div className="problem-grid grid grid-cols-[repeat(auto-fill,minmax(min(100%,20rem),1fr))] gap-4 sm:gap-5">
            {problems.map((problem) => (
              <ProblemCard key={problem.problem_id} problem={problem} />
            ))}
          </div>
          {hasMore && (
            <div className="mt-8 flex justify-center">
              <Button
                variant="outline"
                onClick={() => loadProblems(offset, sortOption, false)}
                disabled={loadingMore}
                aria-busy={loadingMore}
                className="min-w-32"
              >
                {loadingMore ? (
                  <span className="inline-flex items-center justify-center gap-2">
                    <LoadingSpinner size="sm" />
                    <span>Loading</span>
                  </span>
                ) : (
                  "Load More"
                )}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
