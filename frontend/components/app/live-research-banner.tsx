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

  return (
    <aside
      role="status"
      aria-live="polite"
      aria-atomic="false"
      aria-label="Live research status"
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
        <Card className={cn("research-active p-4")}>
          <div className="flex items-center gap-3">
            <span
              aria-hidden="true"
              className="researching-dot inline-block size-2 rounded-full"
            />
            <Badge variant="researching" className="px-2 font-medium shrink-0">
              Researching
            </Badge>
            <Link
              href={`/memories/${active.problem_id}`}
              aria-label={active.description}
              className={cn(
                "min-w-0 flex-1 line-clamp-1 text-sm text-foreground hover:text-coral",
                focusRing,
                "rounded-sm",
              )}
            >
              <TitleMarkdown content={active.description} insideLink />
            </Link>
            {isFallback && (
              <span className="shrink-0 text-xs text-muted-foreground">
                (reconnecting)
              </span>
            )}
            <Badge
              variant={getConfidenceTier(active.best_confidence)}
              className="text-xs px-2 py-0.5 shrink-0 tabular-nums"
            >
              {Math.round(active.best_confidence * 100)}%
            </Badge>
            <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
              {active.solution_count}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-2 pl-5 text-xs text-muted-foreground">
            <span>started {getRelativeTime(active.research_started_at)}</span>
            {remaining > 0 && (
              <span data-testid="live-research-more">
                +{remaining} more in flight
              </span>
            )}
          </div>
        </Card>
      ) : (
        <Card className="p-4">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span
              aria-hidden="true"
              className="inline-block size-2 rounded-full bg-muted-foreground/40"
            />
            <span>
              {snapshot?.last_cycle_at
                ? `Idle - last cycle ${getRelativeTime(snapshot.last_cycle_at)}`
                : "Idle - awaiting first cycle"}
            </span>
            {isFallback && <span className="text-xs">(reconnecting)</span>}
          </div>
        </Card>
      )}
    </aside>
  );
}

export const LiveResearchBanner = memo(LiveResearchBannerInner);
