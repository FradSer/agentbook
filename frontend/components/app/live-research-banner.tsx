"use client";

import Link from "next/link";
import { memo, type ReactElement, useEffect, useRef, useState } from "react";

import { TitleMarkdown } from "@/components/app/title-markdown";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { focusRing } from "@/lib/focus-ring";
import type { LiveResearchSnapshot } from "@/lib/types";
import { useLiveResearch } from "@/lib/use-live-research";
import { cn, getConfidenceTier, getRelativeTime } from "@/lib/utils";

export type LiveResearchBannerProps = {
  /** Optional REST snapshot to use for initial paint. Lets a server
   *  component pre-fetch the snapshot to avoid an idle->active flash. */
  initialSnapshot?: LiveResearchSnapshot | null;
};

const TICK_INTERVAL_MS = 1_000;
const ARIA_DEBOUNCE_MS = 1_000;

/** Narrow: full-width strip. Wide: compact rectangle beside the hero copy. */
const BANNER_CARD = cn(
  "w-full rounded-lg px-3 py-2.5 sm:px-4 sm:py-3",
  "lg:w-52 lg:rounded-xl lg:p-4 lg:min-h-[7.5rem]",
);

const IDLE_DOT = "inline-block size-2 shrink-0 rounded-full bg-muted-foreground/40";

function summariseSnapshot(snapshot: LiveResearchSnapshot | null): string {
  if (!snapshot) return "";
  if (snapshot.active.length === 0) {
    return snapshot.last_cycle_at
      ? `Idle - last cycle ${getRelativeTime(snapshot.last_cycle_at)}`
      : "Idle - awaiting first cycle";
  }
  const head = snapshot.active[0];
  const more =
    snapshot.active.length > 1 ? `, +${snapshot.active.length - 1} more` : "";
  return `Researching ${head.description}${more}`;
}

function LiveResearchBannerInner(props: LiveResearchBannerProps): ReactElement {
  const { snapshot: liveSnapshot, status } = useLiveResearch();
  const snapshot = liveSnapshot ?? props.initialSnapshot ?? null;

  // 1 s ticker so the relative-time sublabel stays current without parent
  // re-renders. We keep state minimal — just a counter that nudges renders.
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), TICK_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  // Debounced aria-live announcement: collapse rapid transitions into one.
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
  const idleCycleText = snapshot?.last_cycle_at
    ? `last cycle ${getRelativeTime(snapshot.last_cycle_at)}`
    : "awaiting first cycle";

  return (
    <aside
      role="status"
      aria-live="polite"
      aria-atomic="false"
      aria-label="Live research status"
      className="w-full lg:w-auto"
    >
      <span
        data-testid="live-research-announcer"
        className="sr-only"
        // The visible UI carries the live state; this hidden region is the
        // debounced-once-per-second announcement target for screen readers.
      >
        {announcement}
      </span>

      {active ? (
        <Card className={cn(BANNER_CARD, "research-active")}>
          <div
            className={cn(
              "grid items-center gap-x-3 gap-y-1.5",
              "grid-cols-[auto_auto_minmax(0,1fr)_auto_auto]",
              "lg:grid-cols-1 lg:items-start lg:gap-y-2.5",
            )}
          >
            <div className="col-span-2 col-start-1 row-start-1 flex items-center gap-2 lg:col-span-1">
              <span
                aria-hidden="true"
                className="researching-dot inline-block size-2 shrink-0 rounded-full"
              />
              <Badge variant="researching" className="shrink-0 px-2 font-medium">
                Researching
              </Badge>
              {isFallback && (
                <span className="text-xs text-muted-foreground">
                  (reconnecting)
                </span>
              )}
            </div>
            <Link
              href={`/memories/${active.problem_id}`}
              aria-label={active.description}
              className={cn(
                "col-start-3 row-start-1 min-w-0 text-sm text-foreground hover:text-coral",
                "line-clamp-1 lg:col-start-1 lg:row-start-2 lg:line-clamp-3 lg:leading-snug",
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
            <div className="col-span-5 row-start-2 flex items-center gap-2 pl-5 text-xs text-muted-foreground lg:col-span-1 lg:row-start-4 lg:pl-0">
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
        </Card>
      ) : (
        <Card className={BANNER_CARD}>
          <div className="flex items-center gap-3 text-sm text-muted-foreground lg:flex-col lg:items-start lg:justify-center lg:gap-2 lg:py-0.5">
            <span aria-hidden="true" className={cn(IDLE_DOT, "lg:mt-0.5")} />
            <p className="min-w-0 flex-1 truncate leading-snug lg:text-xs lg:leading-snug lg:[text-wrap:pretty] lg:whitespace-normal">
              {snapshot?.last_cycle_at
                ? `Idle - ${idleCycleText}`
                : "Idle - awaiting first cycle"}
            </p>
            {isFallback && (
              <span className="shrink-0 text-xs lg:self-start">(reconnecting)</span>
            )}
          </div>
        </Card>
      )}
    </aside>
  );
}

export const LiveResearchBanner = memo(LiveResearchBannerInner);
