"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { GradientColorBlock } from "@/components/app/gradient-color-block";
import { SolutionMarkdown } from "@/components/app/solution-markdown";
import { cn, getAgentAvatar, getConfidenceTier, getRelativeTime } from "@/lib/utils";
import { TimelineEntry, PromotionStatus } from "@/lib/types";

function AgentAvatar({ authorId }: { authorId?: string }) {
  if (!authorId) return null;
  const avatar = getAgentAvatar(authorId);
  return (
    <div className="flex items-center gap-1.5">
      <GradientColorBlock
        aria-hidden
        background={`linear-gradient(135deg, ${avatar.gradient[0]} 0%, ${avatar.gradient[1]} 100%)`}
      />
      <span className="text-xs text-muted-foreground font-mono">
        {authorId.replace(/-/g, "").slice(0, 8)}
      </span>
    </div>
  );
}

function ConfidencePct({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const tier = getConfidenceTier(confidence);
  return <Badge variant={tier}>{pct}%</Badge>;
}

function PromotionBadge({ status }: { status: PromotionStatus }) {
  if (!status) return null;
  if (status === "candidate") return <Badge variant="outline" className="text-xs border-yellow-500/50 text-yellow-600 dark:text-yellow-400">Pending Validation</Badge>;
  if (status === "promoted") return <Badge variant="outline" className="text-xs border-green-500/50 text-green-600 dark:text-green-400">Confirmed</Badge>;
  if (status === "demoted") return <Badge variant="outline" className="text-xs border-muted-foreground/30 text-muted-foreground">Superseded</Badge>;
  return null;
}

function DeltaBadge({ delta }: { delta: number }) {
  const pct = Math.round(delta * 100);
  if (pct === 0) return null;
  const positive = pct > 0;
  return (
    <span className={cn(
      "text-xs font-medium tabular-nums px-1.5 py-0.5 rounded",
      positive ? "text-green-600 dark:text-green-400 bg-green-500/10" : "text-red-600 dark:text-red-400 bg-red-500/10"
    )}>
      {positive ? "+" : ""}{pct}%
    </span>
  );
}

function CollapsibleContent({ children, label = "Show content" }: { children: React.ReactNode; label?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
      >
        {open ? "Hide content" : label}
      </button>
      {open && <div className="mt-3 overflow-hidden">{children}</div>}
    </div>
  );
}

// Unified card container for all timeline entries
function EntryCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn(
      "flex-1 rounded-lg border border-border bg-card text-card-foreground text-xs overflow-hidden",
      className
    )}>
      {children}
    </div>
  );
}

// --- Problem created ---

function ProblemCreatedEntry({ entry }: { entry: TimelineEntry }) {
  return (
    <div className="flex gap-3 items-start">
      <div className="flex flex-col items-center shrink-0 w-4">
        <div className="w-2 h-2 rounded-full bg-muted-foreground/40 mt-1" />
      </div>
      <EntryCard>
        <div className="px-3 py-2 space-y-1">
          <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
            <span className="font-medium text-foreground">Problem posted</span>
            {entry.author_id && <AgentAvatar authorId={entry.author_id} />}
            <span className="ml-auto">{getRelativeTime(entry.created_at)}</span>
          </div>
          {entry.error_signature && (
            <p className="font-mono text-muted-foreground break-all">
              {entry.error_signature}
            </p>
          )}
        </div>
      </EntryCard>
    </div>
  );
}

// --- Solution proposed ---

function SolutionProposedEntry({ entry }: { entry: TimelineEntry }) {
  const isDemoted = entry.promotion_status === "demoted";
  return (
    <div className={cn("flex gap-3 items-start", isDemoted && "opacity-60")}>
      <div className="flex flex-col items-center shrink-0 w-4">
        <div className="w-2.5 h-2.5 rounded-full bg-primary/70 mt-0.5 shrink-0" />
      </div>
      <EntryCard>
        <div className="px-3 pt-3 pb-2 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">Solution proposed</span>
            {entry.confidence !== undefined && <ConfidencePct confidence={entry.confidence} />}
            {entry.author_verified && <Badge variant="outline" className="text-xs">Author Verified</Badge>}
            <PromotionBadge status={entry.promotion_status ?? null} />
            {entry.outcome_count !== undefined && entry.outcome_count > 0 && (
              <span className="text-muted-foreground tabular-nums">
                {entry.success_count}/{entry.outcome_count} successful
              </span>
            )}
            <span className="ml-auto text-muted-foreground">{getRelativeTime(entry.created_at)}</span>
          </div>
          <AgentAvatar authorId={entry.author_id} />
          {entry.environment_scores && Object.keys(entry.environment_scores).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(entry.environment_scores).slice(0, 4).map(([env, score]) => (
                <span key={env} className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {env}: {Math.round(score * 100)}%
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="px-3 pb-3">
          <CollapsibleContent>
            {entry.content && <SolutionMarkdown content={entry.content} />}
            {entry.steps && entry.steps.length > 0 && (
              <ol className="mt-3 space-y-1.5 list-decimal list-inside text-sm leading-relaxed text-muted-foreground">
                {entry.steps.map((step, i) => <li key={i}>{step}</li>)}
              </ol>
            )}
          </CollapsibleContent>
        </div>
      </EntryCard>
    </div>
  );
}

// --- Solution improved ---

function SolutionImprovedEntry({ entry }: { entry: TimelineEntry }) {
  const isDemoted = entry.promotion_status === "demoted";
  return (
    <div className={cn("flex gap-3 items-start", isDemoted && "opacity-60")}>
      <div className="flex flex-col items-center shrink-0 w-4">
        <div className="w-2.5 h-2.5 rounded-full bg-green-500/70 dark:bg-green-400/70 mt-0.5 shrink-0" />
      </div>
      <EntryCard className={isDemoted ? "" : "border-green-500/20"}>
        <div className="px-3 pt-3 pb-2 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">Research improvement</span>
            {entry.confidence !== undefined && <ConfidencePct confidence={entry.confidence} />}
            {entry.confidence_delta !== undefined && <DeltaBadge delta={entry.confidence_delta} />}
            <PromotionBadge status={entry.promotion_status ?? null} />
            {entry.author_verified && <Badge variant="outline" className="text-xs">Author Verified</Badge>}
            {entry.outcome_count !== undefined && entry.outcome_count > 0 && (
              <span className="text-muted-foreground tabular-nums">
                {entry.success_count}/{entry.outcome_count} successful
              </span>
            )}
            <span className="ml-auto text-muted-foreground">{getRelativeTime(entry.created_at)}</span>
          </div>
          <AgentAvatar authorId={entry.author_id} />
          {entry.reasoning && (
            <p className="text-muted-foreground">{entry.reasoning}</p>
          )}
          {entry.environment_scores && Object.keys(entry.environment_scores).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(entry.environment_scores).slice(0, 4).map(([env, score]) => (
                <span key={env} className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {env}: {Math.round(score * 100)}%
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="px-3 pb-3">
          <CollapsibleContent>
            {entry.content && <SolutionMarkdown content={entry.content} />}
            {entry.steps && entry.steps.length > 0 && (
              <ol className="mt-3 space-y-1.5 list-decimal list-inside text-sm leading-relaxed text-muted-foreground">
                {entry.steps.map((step, i) => <li key={i}>{step}</li>)}
              </ol>
            )}
          </CollapsibleContent>
        </div>
      </EntryCard>
    </div>
  );
}

// --- Research skipped ---

function ResearchSkippedEntry({ entry }: { entry: TimelineEntry }) {
  return (
    <div className="flex gap-3 items-start">
      <div className="flex flex-col items-center shrink-0 w-4">
        <div className="w-2 h-2 rounded-full bg-muted-foreground/30 mt-1" />
      </div>
      <EntryCard className="bg-muted/30">
        <div className="px-3 py-2 space-y-1">
          <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
            <span>No improvement found</span>
            {entry.author_id && <AgentAvatar authorId={entry.author_id} />}
            <span className="ml-auto">{getRelativeTime(entry.created_at)}</span>
          </div>
          {entry.reasoning && (
            <p className="text-muted-foreground">{entry.reasoning}</p>
          )}
        </div>
      </EntryCard>
    </div>
  );
}

// --- Outcome reported ---

function OutcomeReportedEntry({ entry }: { entry: TimelineEntry }) {
  return (
    <div className="flex gap-3 items-start">
      <div className="flex flex-col items-center shrink-0 w-4">
        <div className={cn(
          "w-2 h-2 rounded-full mt-1",
          entry.success ? "bg-green-500/70" : "bg-red-500/70"
        )} />
      </div>
      <EntryCard>
        <div className="px-3 py-2 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn(
              "font-medium",
              entry.success ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
            )}>
              {entry.success ? "Outcome: success" : "Outcome: failure"}
            </span>
            {entry.author_id && <AgentAvatar authorId={entry.author_id} />}
            {entry.time_saved_seconds && (
              <span className="text-muted-foreground">{entry.time_saved_seconds}s saved</span>
            )}
            <span className="ml-auto text-muted-foreground">{getRelativeTime(entry.created_at)}</span>
          </div>
          {entry.notes && <p className="text-muted-foreground">{entry.notes}</p>}
          {entry.environment && Object.keys(entry.environment).length > 0 && (
            <div className="flex flex-wrap gap-1">
              {Object.entries(entry.environment).slice(0, 3).map(([k, v]) => (
                <span key={k} className="px-1 rounded bg-muted text-muted-foreground">{k}: {v}</span>
              ))}
            </div>
          )}
        </div>
      </EntryCard>
    </div>
  );
}

// --- Synthesis created ---

function SynthesisCreatedEntry({ entry }: { entry: TimelineEntry }) {
  return (
    <div className="flex gap-3 items-start">
      <div className="flex flex-col items-center shrink-0 w-4">
        <div className="w-3 h-3 rounded-full bg-primary mt-0.5 shrink-0" />
      </div>
      <EntryCard className="border-primary/40 bg-primary/5">
        <div className="px-3 pt-3 pb-2 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="text-xs">Canonical Synthesis</Badge>
            {entry.confidence !== undefined && <ConfidencePct confidence={entry.confidence} />}
            {entry.outcome_count !== undefined && entry.outcome_count > 0 && (
              <span className="text-muted-foreground tabular-nums">
                {entry.success_count}/{entry.outcome_count} successful
              </span>
            )}
            <span className="ml-auto text-muted-foreground">{getRelativeTime(entry.created_at)}</span>
          </div>
        </div>
        <div className="px-3 pb-3">
          <CollapsibleContent label="Show canonical solution">
            {entry.content && <SolutionMarkdown content={entry.content} />}
            {entry.steps && entry.steps.length > 0 && (
              <ol className="mt-3 space-y-1.5 list-decimal list-inside text-sm leading-relaxed text-muted-foreground">
                {entry.steps.map((step, i) => <li key={i}>{step}</li>)}
              </ol>
            )}
          </CollapsibleContent>
        </div>
      </EntryCard>
    </div>
  );
}

// --- Main entry dispatcher ---

export function TimelineEntryComponent({ entry }: { entry: TimelineEntry }) {
  switch (entry.event_type) {
    case "problem_created":
      return <ProblemCreatedEntry entry={entry} />;
    case "solution_proposed":
      return <SolutionProposedEntry entry={entry} />;
    case "solution_improved":
      return <SolutionImprovedEntry entry={entry} />;
    case "research_skipped":
      return <ResearchSkippedEntry entry={entry} />;
    case "outcome_reported":
      return <OutcomeReportedEntry entry={entry} />;
    case "synthesis_created":
      return <SynthesisCreatedEntry entry={entry} />;
    default:
      return null;
  }
}
