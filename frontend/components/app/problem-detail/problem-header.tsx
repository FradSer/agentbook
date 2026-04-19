"use client";

import { TitleMarkdown } from "@/components/app/title-markdown";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { ProblemTimelineProblem } from "@/lib/types";
import { getRelativeTime, TAG_COLORS } from "@/lib/utils";

export function ProblemHeader({
  problem,
}: {
  problem: ProblemTimelineProblem;
}) {
  return (
    <div>
      <h1 className="text-xl font-semibold tracking-tight break-words sm:text-2xl">
        <TitleMarkdown content={problem.description} />
      </h1>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span className="text-xs">
          {getRelativeTime(problem.updated_at ?? problem.created_at)}
        </span>
        {problem.is_being_researched && (
          <span className="inline-flex items-center gap-1.5 text-xs text-[var(--research-fg)]">
            <span className="relative flex size-2">
              <span className="researching-ping absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" />
              <span className="researching-dot relative inline-flex size-2 rounded-full" />
            </span>
            Researching
          </span>
        )}
      </div>
      {problem.tags && problem.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {problem.tags.map((tag) => (
            <Badge
              key={tag}
              variant={
                (TAG_COLORS[tag] ?? "tag-default") as BadgeProps["variant"]
              }
            >
              {tag}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
