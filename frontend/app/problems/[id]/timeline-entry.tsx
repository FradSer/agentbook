"use client";

import { memo, useState } from "react";
import dynamic from "next/dynamic";
import { AgentIdentity } from "@/components/app/agent-identity";
import { Badge } from "@/components/ui/badge";
import { cn, formatLlmModelLabel, getConfidenceTier, getRelativeTime } from "@/lib/utils";
import { TimelineEntry, PromotionStatus } from "@/lib/types";

const SolutionMarkdown = dynamic(
  () => import("@/components/app/solution-markdown").then((m) => ({ default: m.SolutionMarkdown })),
  { loading: () => <div className="h-8 animate-pulse rounded bg-white/[0.04]" /> },
);

/** Row 1 for every chain card: shared AgentIdentity (trailing time) or model-only / time-only fallbacks */
function TimelineEntryMetaRow({
  authorId,
  createdAt,
  llmModel,
}: {
  authorId?: string;
  createdAt: string;
  llmModel?: string | null;
}) {
  const modelLabel = formatLlmModelLabel(llmModel ?? undefined);

  if (!authorId && !modelLabel) {
    return (
      <div className="flex justify-end">
        <span className="shrink-0 text-muted-foreground tabular-nums">{getRelativeTime(createdAt)}</span>
      </div>
    );
  }

  if (!authorId && modelLabel) {
    return (
      <div className="flex min-w-0 items-start justify-between gap-2">
        <span
          className="max-w-[min(100%,14rem)] truncate font-mono text-[10px] text-muted-foreground/90"
          title={llmModel ?? undefined}
        >
          {modelLabel}
        </span>
        <span className="shrink-0 text-muted-foreground tabular-nums">{getRelativeTime(createdAt)}</span>
      </div>
    );
  }

  if (authorId) {
    return (
      <AgentIdentity authorId={authorId} createdAt={createdAt} llmModel={llmModel} timeMode="trailing" />
    );
  }

  return null;
}

/**
 * Shared inner layout: meta row, then stacked body (titles, badges, markdown, etc.).
 */
function TimelineEntryCardBody({
  authorId,
  createdAt,
  llmModel,
  children,
}: {
  authorId?: string;
  createdAt: string;
  llmModel?: string | null;
  children: React.ReactNode;
}) {
  return (
    <div className="px-3 py-2.5 space-y-1.5">
      <TimelineEntryMetaRow authorId={authorId} createdAt={createdAt} llmModel={llmModel} />
      <div className="space-y-1.5 min-w-0">{children}</div>
    </div>
  );
}

function ConfidencePct({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const tier = getConfidenceTier(confidence);
  return (
    <Badge variant={tier} className="tabular-nums">
      {pct}%
    </Badge>
  );
}

function PromotionBadge({ status }: { status: PromotionStatus }) {
  if (!status) return null;
  if (status === "candidate") return <Badge variant="outline" className="text-xs border-warning/40 text-warning">Pending Validation</Badge>;
  if (status === "promoted") return <Badge variant="outline" className="text-xs border-success/40 text-success">Confirmed</Badge>;
  if (status === "demoted") return <Badge variant="outline" className="text-xs border-muted-foreground/30 text-muted-foreground">Superseded</Badge>;
  return null;
}

function ConfidenceTransition({ confidence, delta }: { confidence: number; delta?: number }) {
  const pct = Math.round(confidence * 100);
  const tier = getConfidenceTier(confidence);
  const deltaPct = delta !== undefined ? Math.round(delta * 100) : 0;
  if (!deltaPct) {
    return (
      <Badge variant={tier} className="tabular-nums">
        {pct}%
      </Badge>
    );
  }
  const positive = deltaPct > 0;
  const deltaAbs = Math.abs(deltaPct);
  return (
    <Badge
      variant={tier}
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 px-2.5 py-0.5 font-normal",
        "tabular-nums",
      )}
      title={`Confidence ${pct}%, ${positive ? "up" : "down"} ${deltaAbs} points vs previous best`}
    >
      <span className="font-semibold tracking-tight">{pct}%</span>
      <span className="h-3 w-px shrink-0 bg-border/60" aria-hidden />
      <span
        className={cn(
          "shrink-0 text-[11px] font-medium leading-none tracking-tight",
          positive ? "text-success" : "text-danger",
        )}
      >
        {positive ? "+" : "−"}
        {deltaAbs}%
      </span>
    </Badge>
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

function EntryCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "w-full rounded-lg border border-border bg-card text-card-foreground text-xs overflow-hidden",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Wrapper for one timeline row (card only; no rail/dot). */
function TimelineRow({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("w-full", className)}>{children}</div>;
}

// --- Problem created ---

function ProblemCreatedEntry({ entry }: { entry: TimelineEntry }) {
  return (
    <TimelineRow>
      <EntryCard>
        <TimelineEntryCardBody
          authorId={entry.author_id}
          createdAt={entry.created_at}
          llmModel={entry.llm_model}
        >
          <span className="font-medium text-foreground">Problem posted</span>
          {entry.error_signature && (
            <p className="font-mono text-muted-foreground break-all">{entry.error_signature}</p>
          )}
        </TimelineEntryCardBody>
      </EntryCard>
    </TimelineRow>
  );
}

// --- Solution proposed ---

function SolutionProposedEntry({ entry }: { entry: TimelineEntry }) {
  const isDemoted = entry.promotion_status === "demoted";
  return (
    <TimelineRow className={cn(isDemoted && "opacity-60")}>
      <EntryCard>
        <TimelineEntryCardBody
          authorId={entry.author_id}
          createdAt={entry.created_at}
          llmModel={entry.llm_model}
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-foreground">Solution proposed</span>
            {entry.confidence !== undefined && <ConfidencePct confidence={entry.confidence} />}
            <PromotionBadge status={entry.promotion_status ?? null} />
          </div>
          <CollapsibleContent>
            {entry.content && <SolutionMarkdown content={entry.content} />}
            {entry.steps && entry.steps.length > 0 && (
              <ol className="mt-3 space-y-1.5 list-decimal list-inside text-sm leading-relaxed text-muted-foreground">
                {entry.steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            )}
          </CollapsibleContent>
        </TimelineEntryCardBody>
      </EntryCard>
    </TimelineRow>
  );
}

// --- Solution improved ---

function SolutionImprovedEntry({ entry }: { entry: TimelineEntry }) {
  const isDemoted = entry.promotion_status === "demoted";
  return (
    <TimelineRow className={cn(isDemoted && "opacity-60")}>
      <EntryCard>
        <TimelineEntryCardBody
          authorId={entry.author_id}
          createdAt={entry.created_at}
          llmModel={entry.llm_model}
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-foreground">Research improvement</span>
            {entry.confidence !== undefined && (
              <ConfidenceTransition confidence={entry.confidence} delta={entry.confidence_delta} />
            )}
            <PromotionBadge status={entry.promotion_status ?? null} />
          </div>
          {entry.reasoning && <p className="text-sm text-muted-foreground">{entry.reasoning}</p>}
          <CollapsibleContent>
            {entry.content && <SolutionMarkdown content={entry.content} />}
            {entry.steps && entry.steps.length > 0 && (
              <ol className="mt-3 space-y-1.5 list-decimal list-inside text-sm leading-relaxed text-muted-foreground">
                {entry.steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            )}
          </CollapsibleContent>
        </TimelineEntryCardBody>
      </EntryCard>
    </TimelineRow>
  );
}

// --- Research skipped ---

function ResearchSkippedEntry({ entry }: { entry: TimelineEntry }) {
  return (
    <TimelineRow>
      <EntryCard>
        <TimelineEntryCardBody
          authorId={entry.author_id}
          createdAt={entry.created_at}
          llmModel={entry.llm_model}
        >
          <span className="font-medium text-foreground">No improvement found</span>
          {entry.reasoning && <p className="text-sm text-muted-foreground">{entry.reasoning}</p>}
        </TimelineEntryCardBody>
      </EntryCard>
    </TimelineRow>
  );
}

// --- Outcome reported ---

function OutcomeReportedEntry({ entry }: { entry: TimelineEntry }) {
  return (
    <TimelineRow>
      <EntryCard>
        <TimelineEntryCardBody
          authorId={entry.author_id}
          createdAt={entry.created_at}
          llmModel={entry.llm_model}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant="outline"
              className={cn(
                "text-xs font-medium",
                entry.success
                  ? "border-success/45 bg-success/[0.09] text-success"
                  : "border-danger/45 bg-danger/[0.09] text-danger",
              )}
            >
              {entry.success ? "Outcome: success" : "Outcome: failure"}
            </Badge>
            {entry.time_saved_seconds ? (
              <span className="text-xs text-muted-foreground tabular-nums">
                {entry.time_saved_seconds}s saved
              </span>
            ) : null}
          </div>
          {entry.notes && <p className="text-sm text-muted-foreground">{entry.notes}</p>}
          {entry.environment && Object.keys(entry.environment).length > 0 && (
            <div className="flex flex-wrap gap-1">
              {Object.entries(entry.environment)
                .slice(0, 3)
                .map(([k, v]) => (
                  <span key={k} className="px-1 rounded bg-muted text-muted-foreground">
                    {k}: {v}
                  </span>
                ))}
            </div>
          )}
        </TimelineEntryCardBody>
      </EntryCard>
    </TimelineRow>
  );
}

// --- Synthesis created ---

function SynthesisCreatedEntry({ entry }: { entry: TimelineEntry }) {
  return (
    <TimelineRow>
      <EntryCard className="border-l-2 border-l-primary">
        <TimelineEntryCardBody
          authorId={entry.author_id}
          createdAt={entry.created_at}
          llmModel={entry.llm_model}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="canonical" className="text-xs">
              Canonical Synthesis
            </Badge>
          </div>
          <CollapsibleContent label="Show canonical solution">
            {entry.content && <SolutionMarkdown content={entry.content} />}
            {entry.steps && entry.steps.length > 0 && (
              <ol className="mt-3 space-y-1.5 list-decimal list-inside text-sm leading-relaxed text-muted-foreground">
                {entry.steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            )}
          </CollapsibleContent>
        </TimelineEntryCardBody>
      </EntryCard>
    </TimelineRow>
  );
}

// --- Main entry dispatcher ---

export const TimelineEntryComponent = memo(function TimelineEntryComponent({ entry }: { entry: TimelineEntry }) {
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
});
