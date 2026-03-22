"use client";

import { TitleMarkdown } from "@/components/app/title-markdown";
import { formatLlmModelLabel, getRelativeTime, TAG_COLORS } from "@/lib/utils";
import { ProblemTimelineProblem } from "@/lib/types";

export function ProblemHeader({ problem }: { problem: ProblemTimelineProblem }) {
  const modelLabel = formatLlmModelLabel(problem.llm_model ?? undefined);
  return (
    <div>
      <h1 className="text-xl font-semibold tracking-tight break-words sm:text-2xl">
        <TitleMarkdown content={problem.description} />
      </h1>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span className="text-xs">{getRelativeTime(problem.created_at)}</span>
        {modelLabel ? (
          <span className="text-[10px] font-mono text-muted-foreground/90" title={problem.llm_model ?? undefined}>
            {modelLabel}
          </span>
        ) : null}
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
    </div>
  );
}
