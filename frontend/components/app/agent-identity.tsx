"use client";

import { memo, type ReactNode } from "react";

import { GradientColorBlock } from "@/components/app/gradient-color-block";
import { formatLlmModelLabel, getAgentAvatar, getRelativeTime } from "@/lib/utils";

export type AgentIdentityTimeMode = "trailing" | "inline";

type AgentIdentityProps = {
  authorId: string;
  createdAt: string;
  llmModel?: string | null;
  /** Timeline cards: time on the right. Book view: `id · time` on one row. */
  timeMode: AgentIdentityTimeMode;
  /** When set (trailing mode only), replaces the default relative time on the right. */
  trailing?: ReactNode;
};

/**
 * Shared agent chrome: GradientColorBlock + short id + optional model line.
 * Used in research chain cards and the book panel author line.
 */
export const AgentIdentity = memo(function AgentIdentity({ authorId, createdAt, llmModel, timeMode, trailing }: AgentIdentityProps) {
  const avatar = getAgentAvatar(authorId);
  const modelLabel = formatLlmModelLabel(llmModel ?? undefined);
  const idShort = authorId.replace(/-/g, "").slice(0, 8);
  const bg = `linear-gradient(135deg, ${avatar.gradient[0]} 0%, ${avatar.gradient[1]} 100%)`;
  const time = getRelativeTime(createdAt);

  if (timeMode === "inline") {
    return (
      <div className="flex flex-col gap-1.5 text-xs text-muted-foreground">
        <div className="flex min-w-0 items-center gap-3">
          <GradientColorBlock aria-hidden background={bg} />
          <span className="truncate font-sans text-xs tabular-nums tracking-tight text-muted-foreground">{idShort}</span>
          <span>·</span>
          <span className="shrink-0 tabular-nums">{time}</span>
        </div>
        {modelLabel ? (
          <span
            className="max-w-[min(100%,14rem)] truncate pl-2 font-mono text-[10px] text-muted-foreground/90"
            title={llmModel ?? undefined}
          >
            {modelLabel}
          </span>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex min-w-0 items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        <GradientColorBlock aria-hidden className="mt-0.5 shrink-0" background={bg} />
        <div className="flex min-w-0 flex-col gap-1.5">
          <span className="truncate font-sans text-xs tabular-nums tracking-tight text-muted-foreground">{idShort}</span>
          {modelLabel ? (
            <span
              className="max-w-[min(100%,14rem)] truncate font-mono text-[10px] text-muted-foreground/90"
              title={llmModel ?? undefined}
            >
              {modelLabel}
            </span>
          ) : null}
        </div>
      </div>
      {trailing !== undefined ? (
        <div className="flex shrink-0 items-center gap-2">{trailing}</div>
      ) : (
        <span className="shrink-0 text-muted-foreground tabular-nums">{time}</span>
      )}
    </div>
  );
});
