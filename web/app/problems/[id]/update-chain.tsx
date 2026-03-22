"use client";

import { memo } from "react";
import { TimelineEntry } from "@/lib/types";
import { TimelineEntryComponent } from "./timeline-entry";

export const UpdateChain = memo(function UpdateChain({ timeline }: { timeline: TimelineEntry[] }) {
  if (timeline.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No activity yet.</p>
    );
  }

  const reversed = timeline.slice().reverse();

  return (
    <div className="space-y-4">
      {reversed.map((entry, i) => (
        <TimelineEntryComponent key={`${entry.event_type}-${entry.created_at}-${i}`} entry={entry} />
      ))}
    </div>
  );
});
