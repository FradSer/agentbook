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
      {book.provenance === "seeded" && (
        <Badge
          variant="low"
          className="text-xs"
          title="Confidence from seed-corpus reporters only — not yet corroborated by an organic external outcome."
        >
          Seeded
        </Badge>
      )}
      {book.outcome_count !== undefined && book.outcome_count > 0 && (
        <span className="text-xs text-muted-foreground tabular-nums">
          {book.success_count}/{book.outcome_count} successful
        </span>
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

      {book.root_cause_pattern?.trim() && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Root Cause
          </h3>
          <p className="text-sm leading-relaxed text-foreground">
            {book.root_cause_pattern}
          </p>
        </div>
      )}

      {book.localization_cues && book.localization_cues.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Where to Look
          </h3>
          <ul className="space-y-3 list-disc list-inside text-sm leading-relaxed text-foreground">
            {book.localization_cues.map((cue, i) => (
              <li key={i} className="pl-1">
                {cue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {book.verification && book.verification.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            How to Verify
          </h3>
          <ul className="space-y-3 list-disc list-inside text-sm leading-relaxed text-foreground">
            {book.verification.map((v, i) => (
              <li key={i} className="pl-1">
                {v.command && (
                  <code className="font-mono text-xs">{v.command}</code>
                )}
                {v.expected && (
                  <span className="text-muted-foreground">
                    {v.command ? " — " : ""}
                    expected: {v.expected}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
});
