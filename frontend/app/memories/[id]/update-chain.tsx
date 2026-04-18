"use client";

import { memo, useMemo } from "react";
import type { TimelineEntry } from "@/lib/types";
import { TimelineEntryComponent } from "./timeline-entry";

function timelineEntryKey(entry: TimelineEntry, index: number): string {
  const base = [
    entry.event_type,
    entry.created_at,
    entry.solution_id,
    entry.author_id,
    entry.event_type === "outcome_reported" ? String(entry.success) : "",
  ]
    .filter(Boolean)
    .join(":");
  return base || `idx-${index}`;
}

export const UpdateChain = memo(function UpdateChain({
  timeline,
}: {
  timeline: TimelineEntry[];
}) {
  const reversed = useMemo(() => [...timeline].reverse(), [timeline]);

  if (reversed.length === 0) {
    return <p className="text-sm text-muted-foreground">No activity yet.</p>;
  }

  return (
    <div className="timeline-entries space-y-4 [contain:layout]">
      {reversed.map((entry, i) => (
        <TimelineEntryComponent
          key={timelineEntryKey(entry, i)}
          entry={entry}
        />
      ))}
    </div>
  );
});
