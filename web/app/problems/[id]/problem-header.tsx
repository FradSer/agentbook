"use client";

import { Badge } from "@/components/ui/badge";
import { TitleMarkdown } from "@/components/app/title-markdown";
import { getConfidenceTier, getRelativeTime, TAG_COLORS } from "@/lib/utils";
import { ProblemTimelineProblem } from "@/lib/types";

export function ProblemHeader({ problem }: { problem: ProblemTimelineProblem }) {
  const tier = getConfidenceTier(problem.best_confidence);
  const pct = Math.round(problem.best_confidence * 100);

  return (
    <div>
      <h1 className="text-xl font-semibold tracking-tight break-words sm:text-2xl">
        <TitleMarkdown content={problem.description} />
      </h1>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <Badge variant={tier}>{pct}% confidence</Badge>
        {problem.has_canonical && (
          <Badge variant="secondary">Has Canonical</Badge>
        )}
        <span className="text-xs">{getRelativeTime(problem.created_at)}</span>
      </div>
      {problem.tags && problem.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {problem.tags.map((tag) => (
            <span
              key={tag}
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${TAG_COLORS[tag] ?? "tag-default"}`}
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      {problem.error_signature && (
        <p
          className="mt-2 font-mono text-xs text-muted-foreground truncate"
          title={problem.error_signature}
        >
          {problem.error_signature}
        </p>
      )}
    </div>
  );
}
