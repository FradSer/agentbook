"use client";

import dynamic from "next/dynamic";
import { memo } from "react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { BookSolutionPayload } from "@/lib/types";
import { getConfidenceTier } from "@/lib/utils";

const SolutionMarkdown = dynamic(
  () =>
    import("@/components/app/solution-markdown").then((m) => ({
      default: m.SolutionMarkdown,
    })),
  {
    loading: () => <Skeleton className="h-32 rounded-lg" />,
  },
);

/** Badges for the book row — driven by server ``book_solution`` (aligned with canonical). */
export const BookSolutionMetaBar = memo(function BookSolutionMetaBar({
  book,
}: {
  book: BookSolutionPayload | null;
}) {
  if (!book?.content?.trim()) return null;

  const confidence = book.confidence ?? 0;
  const tier = getConfidenceTier(confidence);
  const pct = Math.round(confidence * 100);

  return (
    <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
      {book.is_synthesized && (
        <Badge variant="canonical" className="text-xs">
          Canonical
        </Badge>
      )}
      <Badge variant={tier}>{pct}%</Badge>
      {book.outcome_count !== undefined && book.outcome_count > 0 && (
        <span className="text-xs text-muted-foreground tabular-nums">
          {book.success_count}/{book.outcome_count} successful
        </span>
      )}
      {book.environment_scores &&
        Object.keys(book.environment_scores).length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(book.environment_scores)
              .slice(0, 4)
              .map(([env, score]) => (
                <span
                  key={env}
                  className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
                >
                  {env}: {Math.round(score * 100)}%
                </span>
              ))}
          </div>
        )}
    </div>
  );
});

export const BookView = memo(function BookView({
  book,
}: {
  book: BookSolutionPayload | null;
}) {
  if (!book?.content?.trim()) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-sm text-muted-foreground border border-dashed rounded-lg">
        <span>No solution yet.</span>
        <span className="text-xs mt-1">Auto-research is in progress.</span>
      </div>
    );
  }

  return (
    <article className="w-full min-w-0 space-y-6">
      <SolutionMarkdown content={book.content} />

      {book.steps && book.steps.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Steps
          </h3>
          <ol className="space-y-3 list-decimal list-inside text-sm leading-relaxed text-foreground">
            {book.steps.map((step, i) => (
              <li key={i} className="pl-1">
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}
    </article>
  );
});
