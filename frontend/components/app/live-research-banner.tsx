"use client";

import Link from "next/link";
import { memo, type ReactElement, useEffect, useRef, useState } from "react";

import { TitleMarkdown } from "@/components/app/title-markdown";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { focusRing } from "@/lib/focus-ring";
import type {
  LiveResearchActive,
  LiveResearchRecentCycle,
  LiveResearchSnapshot,
} from "@/lib/types";
import { useLiveResearch } from "@/lib/use-live-research";
import { cn, getConfidenceTier, getRelativeTime } from "@/lib/utils";

export type LiveResearchBannerProps = {
  /** Optional REST snapshot to use for initial paint. Lets a server
   *  component pre-fetch the snapshot to avoid an idle->active flash. */
  initialSnapshot?: LiveResearchSnapshot | null;
};

const TICK_INTERVAL_MS = 1_000;
const ARIA_DEBOUNCE_MS = 1_000;
const RECENT_VISIBLE_LIMIT = 2;

/** Aligns with nav logo: nav pl-3 (12px) + home link pl-2 (8px) = 20px. */
export const BANNER_CONTENT_INSET_X = "px-5";

/** Card shell matches problem list rows; body inset aligns with hero copy. */
const BANNER_CARD = cn(
  "w-full rounded-xl border-border/80 px-0 py-4",
  "lg:w-80 lg:p-5 lg:min-h-[12rem]",
);

const BANNER_CARD_BODY = cn(BANNER_CONTENT_INSET_X, "lg:px-0");

const BANNER_ASIDE = "w-full lg:w-auto";

const IDLE_DOT = "inline-block size-2 shrink-0 rounded-full bg-muted-foreground/40";

function cycleStatusLabel(status: LiveResearchRecentCycle["status"]): string {
  switch (status) {
    case "improved":
      return "Improved";
    case "synthesis_completed":
      return "Synthesized";
    case "no_solution_proposed":
      return "No proposal";
    default:
      return "No change";
  }
}

function summariseSnapshot(snapshot: LiveResearchSnapshot | null): string {
  if (!snapshot) return "";
  if (snapshot.active.length === 0) {
    const idle = snapshot.last_cycle_at
      ? `Idle - last cycle ${getRelativeTime(snapshot.last_cycle_at)}`
      : "Idle - awaiting first cycle";
    const weekly = snapshot.cycles_last_7_days ?? 0;
    return weekly > 0 ? `${idle}. ${weekly} cycles in the last 7 days.` : idle;
  }
  const head = snapshot.active[0];
  const more =
    snapshot.active.length > 1 ? `, +${snapshot.active.length - 1} more` : "";
  return `Researching ${head.description}${more}`;
}

function BannerHeader({
  isActive,
  isFallback,
}: {
  isActive: boolean;
  isFallback: boolean;
}): ReactElement {
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="flex min-w-0 items-center gap-2">
        <span
          aria-hidden="true"
          className={cn(
            isActive ? "researching-dot" : IDLE_DOT,
            "inline-block size-2 shrink-0 rounded-full",
          )}
        />
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          Background research
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {isActive ? (
          <Badge variant="researching" className="px-2 py-0 text-[10px] font-medium">
            Live
          </Badge>
        ) : (
          <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Idle
          </span>
        )}
        {isFallback && (
          <span className="text-[10px] text-muted-foreground">(reconnecting)</span>
        )}
      </div>
    </div>
  );
}

function RecentCyclesList({
  cycles,
  limit = RECENT_VISIBLE_LIMIT,
}: {
  cycles: LiveResearchRecentCycle[];
  limit?: number;
}): ReactElement | null {
  if (cycles.length === 0) return null;
  const visible = cycles.slice(0, limit);

  const renderItem = (cycle: LiveResearchRecentCycle) => (
    <li key={`${cycle.problem_id}-${cycle.created_at}`} className="min-w-0">
      <Link
        href={`/memories/${cycle.problem_id}`}
        className={cn(
          "group flex flex-col gap-0.5 text-xs text-muted-foreground hover:text-foreground",
          focusRing,
          "rounded-sm",
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="shrink-0 font-medium text-foreground/80 group-hover:text-coral">
            {cycleStatusLabel(cycle.status)}
          </span>
          <span className="shrink-0 tabular-nums text-[10px] leading-none">
            {getRelativeTime(cycle.created_at)}
          </span>
        </div>
        <p className="line-clamp-2 min-w-0 leading-snug text-muted-foreground">
          {cycle.description}
        </p>
      </Link>
    </li>
  );

  return (
    <div className="mt-6 border-t border-border/70 pt-6">
      <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
        Recent cycles
      </p>
      <ul className="space-y-2">{visible.map(renderItem)}</ul>
    </div>
  );
}

function BannerStats({
  snapshot,
}: {
  snapshot: LiveResearchSnapshot;
}): ReactElement {
  const weekly = snapshot.cycles_last_7_days ?? 0;
  const lastCycle = snapshot.last_cycle_at
    ? getRelativeTime(snapshot.last_cycle_at)
    : null;

  return (
    <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border/70 pt-6 text-[10px] text-muted-foreground lg:text-xs">
      {weekly > 0 ? (
        <span className="tabular-nums">
          <span className="font-medium text-foreground/80">{weekly}</span> cycles
          in 7d
        </span>
      ) : (
        <span>No cycles in the last 7 days</span>
      )}
      {lastCycle ? (
        <span className="tabular-nums">
          Last run <span className="text-foreground/80">{lastCycle}</span>
        </span>
      ) : (
        <span>Awaiting first cycle</span>
      )}
    </div>
  );
}

function ActiveResearchPanel({
  active,
  remaining,
}: {
  active: LiveResearchActive;
  remaining: number;
}): ReactElement {
  return (
    <div
      className={cn(
        "mt-6 grid items-center gap-x-3 gap-y-1.5",
        "grid-cols-[auto_auto_minmax(0,1fr)_auto_auto]",
        "lg:grid-cols-1 lg:items-start lg:gap-y-2",
      )}
    >
      <Badge
        variant="researching"
        className="col-span-2 col-start-1 row-start-1 shrink-0 px-2 py-0.5 text-xs font-medium lg:col-span-1"
      >
        Researching
      </Badge>
      <Link
        href={`/memories/${active.problem_id}`}
        aria-label={active.description}
        className={cn(
          "col-start-3 row-start-1 min-w-0 text-sm text-foreground hover:text-coral",
          "line-clamp-1 lg:col-start-1 lg:row-start-2 lg:line-clamp-2 lg:leading-snug",
          focusRing,
          "rounded-sm",
        )}
      >
        <TitleMarkdown content={active.description} insideLink />
      </Link>
      <div className="col-span-2 col-start-4 row-start-1 flex items-center justify-end gap-2 lg:col-span-1 lg:col-start-1 lg:row-start-3 lg:w-full lg:justify-between">
        <Badge
          variant={getConfidenceTier(active.best_confidence)}
          className="shrink-0 px-2 py-0.5 text-xs tabular-nums"
        >
          {Math.round(active.best_confidence * 100)}%
        </Badge>
        <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
          {active.solution_count}
          <span className="hidden lg:inline"> solutions</span>
        </span>
      </div>
      <div className="col-span-5 row-start-2 flex items-center gap-2 pl-0 text-xs text-muted-foreground lg:col-span-1 lg:row-start-4">
        <span>started {getRelativeTime(active.research_started_at)}</span>
        {remaining > 0 && (
          <span data-testid="live-research-more">
            <span className="lg:hidden">+{remaining} more in flight</span>
            <span className="hidden lg:inline">
              {" "}
              · +{remaining} more
            </span>
          </span>
        )}
      </div>
    </div>
  );
}

function BannerSkeleton(): ReactElement {
  return (
    <Card className={BANNER_CARD} aria-hidden="true">
      <div className={BANNER_CARD_BODY}>
        <div className="flex items-center justify-between gap-2">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-4 w-10 rounded-full" />
        </div>
        <div className="mt-4 space-y-2">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
        </div>
        <div className="mt-6 border-t border-border/70 pt-6">
          <Skeleton className="mb-2 h-2.5 w-20" />
          <div className="space-y-3">
            {Array.from({ length: RECENT_VISIBLE_LIMIT }, (_, i) => (
              <div key={i} className="space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="h-2.5 w-12" />
                </div>
                <Skeleton className="h-3 w-full" />
              </div>
            ))}
          </div>
        </div>
        <div className="mt-6 flex gap-3 border-t border-border/70 pt-6">
          <Skeleton className="h-2.5 w-20" />
          <Skeleton className="h-2.5 w-24" />
        </div>
      </div>
    </Card>
  );
}

function LiveResearchBannerInner(props: LiveResearchBannerProps): ReactElement {
  const { snapshot: liveSnapshot, status } = useLiveResearch();
  const snapshot = liveSnapshot ?? props.initialSnapshot ?? null;
  const isLoading = status === "loading" && snapshot === null;

  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), TICK_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  const [announcement, setAnnouncement] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const summary = summariseSnapshot(snapshot);
  useEffect(() => {
    if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setAnnouncement(summary);
    }, ARIA_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    };
  }, [summary]);

  const isFallback = status === "fallback";
  const active = snapshot?.active[0];
  const remaining = snapshot ? Math.max(0, snapshot.active.length - 1) : 0;
  const recentCycles = snapshot?.recent_cycles ?? [];

  if (isLoading) {
    return (
      <aside
        role="status"
        aria-busy="true"
        aria-label="Live research status"
        className={BANNER_ASIDE}
      >
        <span className="sr-only">Loading research status</span>
        <BannerSkeleton />
      </aside>
    );
  }

  return (
    <aside
      role="status"
      aria-live="polite"
      aria-atomic="false"
      aria-label="Live research status"
      className={BANNER_ASIDE}
    >
      <span data-testid="live-research-announcer" className="sr-only">
        {announcement}
      </span>

      <Card
        className={cn(BANNER_CARD, active ? "research-active" : undefined)}
      >
        <div className={BANNER_CARD_BODY}>
          <BannerHeader isActive={Boolean(active)} isFallback={isFallback} />

          {active ? (
            <ActiveResearchPanel active={active} remaining={remaining} />
          ) : (
            <p className="mt-4 text-xs leading-snug text-muted-foreground lg:text-sm">
              {snapshot?.last_cycle_at
                ? `Reviewer agent is between cycles. Last completed run ${getRelativeTime(snapshot.last_cycle_at)}.`
                : "Reviewer agent has not completed a research cycle yet."}
            </p>
          )}

          {snapshot ? (
            <>
              <RecentCyclesList cycles={recentCycles} />
              <BannerStats snapshot={snapshot} />
            </>
          ) : null}
        </div>
      </Card>
    </aside>
  );
}

export const LiveResearchBanner = memo(LiveResearchBannerInner);
