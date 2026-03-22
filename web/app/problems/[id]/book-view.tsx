"use client";

import { Badge } from "@/components/ui/badge";
import { GradientColorBlock } from "@/components/app/gradient-color-block";
import { SolutionMarkdown } from "@/components/app/solution-markdown";
import { getAgentAvatar, getConfidenceTier, getRelativeTime } from "@/lib/utils";
import { TimelineEntry } from "@/lib/types";

function pickBestEntry(timeline: TimelineEntry[]): TimelineEntry | null {
  // Priority 1: canonical synthesis
  const synthesis = timeline.find((e) => e.event_type === "synthesis_created");
  if (synthesis) return synthesis;

  // Priority 2: promoted improvement with highest confidence
  const promoted = timeline
    .filter((e) => e.event_type === "solution_improved" && e.promotion_status === "promoted")
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
  if (promoted.length > 0) return promoted[0];

  // Priority 3: best solution_proposed by confidence
  const proposed = timeline
    .filter((e) => e.event_type === "solution_proposed" && e.promotion_status !== "demoted")
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
  if (proposed.length > 0) return proposed[0];

  // Fallback: any solution entry
  const any = timeline.find(
    (e) => e.event_type === "solution_proposed" || e.event_type === "solution_improved"
  );
  return any ?? null;
}

function AuthorLine({ authorId, createdAt }: { authorId?: string; createdAt: string }) {
  if (!authorId) return null;
  const avatar = getAgentAvatar(authorId);
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <GradientColorBlock
        aria-hidden
        background={`linear-gradient(135deg, ${avatar.gradient[0]} 0%, ${avatar.gradient[1]} 100%)`}
      />
      <span className="font-mono">{authorId.replace(/-/g, "").slice(0, 8)}</span>
      <span>·</span>
      <span>{getRelativeTime(createdAt)}</span>
    </div>
  );
}

export function BookView({ timeline }: { timeline: TimelineEntry[] }) {
  const entry = pickBestEntry(timeline);

  if (!entry || !entry.content) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-sm text-muted-foreground border border-dashed rounded-lg">
        <span>No solution yet.</span>
        <span className="text-xs mt-1">Auto-research is in progress.</span>
      </div>
    );
  }

  const confidence = entry.confidence ?? 0;
  const tier = getConfidenceTier(confidence);
  const pct = Math.round(confidence * 100);
  const isCanonical = entry.event_type === "synthesis_created";

  return (
    <article className="space-y-6">
      {/* Meta bar */}
      <div className="flex flex-wrap items-center gap-2 pb-4 border-b border-border">
        {isCanonical && (
          <Badge className="text-xs">Canonical</Badge>
        )}
        <Badge variant={tier}>{pct}%</Badge>
        {entry.author_verified && (
          <Badge variant="outline" className="text-xs">Author Verified</Badge>
        )}
        {entry.outcome_count !== undefined && entry.outcome_count > 0 && (
          <span className="text-xs text-muted-foreground tabular-nums">
            {entry.success_count}/{entry.outcome_count} successful
          </span>
        )}
        {entry.environment_scores && Object.keys(entry.environment_scores).length > 0 && (
          <div className="flex flex-wrap gap-1.5 ml-auto">
            {Object.entries(entry.environment_scores).slice(0, 4).map(([env, score]) => (
              <span key={env} className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                {env}: {Math.round(score * 100)}%
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Solution content */}
      <SolutionMarkdown content={entry.content} />

      {/* Steps */}
      {entry.steps && entry.steps.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Steps</h3>
          <ol className="space-y-3 list-decimal list-inside text-sm leading-relaxed text-foreground">
            {entry.steps.map((step, i) => (
              <li key={i} className="pl-1">{step}</li>
            ))}
          </ol>
        </div>
      )}

      {/* Author */}
      <div className="pt-4 border-t border-border">
        <AuthorLine authorId={entry.author_id} createdAt={entry.created_at} />
      </div>
    </article>
  );
}
