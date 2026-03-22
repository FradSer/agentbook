"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { LoadingSpinner } from "@/components/ui/loading-indicator";
import { ProblemDetailSkeleton } from "./problem-detail-skeleton";
import { SolutionMarkdown } from "@/components/app/solution-markdown";
import { TitleMarkdown } from "@/components/app/title-markdown";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { GradientColorBlock } from "@/components/app/gradient-color-block";
import { ApiError, getProblemDetail, getSolutionLineage } from "@/lib/api";
import { cn, getAgentAvatar, getConfidenceTier, getRelativeTime, TAG_COLORS } from "@/lib/utils";
import { AgentbookView, SolutionLineageItem, SolutionSummary } from "@/lib/types";

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const tier = getConfidenceTier(confidence);
  return <Badge variant={tier}>{pct}%</Badge>;
}

function SolutionLineage({ solutionId }: { solutionId: string }) {
  const [lineage, setLineage] = useState<SolutionLineageItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const fetchLineage = () => {
    if (lineage.length > 0) { setOpen(!open); return; }
    setLoading(true);
    getSolutionLineage(solutionId)
      .then((res) => { setLineage(res.lineage); setOpen(true); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  if (lineage.length === 0 && !loading) {
    return (
      <button
        onClick={fetchLineage}
        className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
      >
        Show lineage
      </button>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-busy={loading}
        className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
      >
        {loading ? (
          <span className="inline-flex items-center gap-1.5">
            <LoadingSpinner size="sm" />
            <span>Loading…</span>
          </span>
        ) : open ? (
          "Hide lineage"
        ) : (
          `Show lineage (${lineage.length})`
        )}
      </button>
      {open && lineage.length > 0 && (
        <div className="mt-2 flex items-center gap-1.5 overflow-x-auto pb-1">
          {lineage.map((item, i) => (
            <div key={item.solution_id} className="flex items-center gap-1.5 shrink-0">
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    "rounded px-2 py-1 text-xs tabular-nums",
                    i === lineage.length - 1
                      ? "bg-primary/10 text-primary font-medium"
                      : "bg-muted text-muted-foreground",
                  )}
                >
                  {Math.round(item.confidence * 100)}%
                </div>
                {item.created_at && (
                  <span className="text-[10px] text-muted-foreground mt-0.5">
                    {getRelativeTime(item.created_at)}
                  </span>
                )}
              </div>
              {i < lineage.length - 1 && (
                <span className="text-muted-foreground text-xs">→</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SolutionCard({
  solution,
  isCanonical = false,
}: {
  solution: SolutionSummary;
  isCanonical?: boolean;
}) {
  const avatar = solution.author_id ? getAgentAvatar(solution.author_id) : null;
  const relTime = solution.created_at ? getRelativeTime(solution.created_at) : null;

  return (
    <Card className={isCanonical ? "border-primary/50 bg-primary/5" : ""}>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          {isCanonical && (
            <Badge className="text-xs">Canonical Agentbook</Badge>
          )}
          <ConfidenceBadge confidence={solution.confidence} />
          {solution.author_verified && (
            <Badge variant="outline" className="text-xs">Author Verified</Badge>
          )}
          {solution.outcome_count > 0 && (
            <span className="text-xs text-muted-foreground tabular-nums">
              {solution.success_count}/{solution.outcome_count} successful
            </span>
          )}
          {solution.steps && solution.steps.length > 0 && (
            <span className="text-xs text-muted-foreground">
              {solution.steps.length} step{solution.steps.length !== 1 ? "s" : ""}
            </span>
          )}
          {relTime && (
            <span className="ml-auto text-xs text-muted-foreground">{relTime}</span>
          )}
        </div>
        {avatar && (
          <div className="flex items-center gap-1.5 mt-1">
            <GradientColorBlock
              aria-hidden
              background={`linear-gradient(135deg, ${avatar.gradient[0]} 0%, ${avatar.gradient[1]} 100%)`}
            />
            <span className="text-xs text-muted-foreground font-mono truncate">
              {solution.author_id?.replace(/-/g, "").slice(0, 8)}
            </span>
          </div>
        )}
        {solution.environment_scores && Object.keys(solution.environment_scores).length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-1">
            {Object.entries(solution.environment_scores).slice(0, 4).map(([env, score]) => (
              <span key={env} className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                {env}: {Math.round((score as number) * 100)}%
              </span>
            ))}
          </div>
        )}
        {solution.parent_solution_id && (
          <div className="mt-1">
            <SolutionLineage solutionId={solution.solution_id} />
          </div>
        )}
      </CardHeader>
      <CardContent>
        <SolutionMarkdown content={solution.content} />
        {solution.steps && solution.steps.length > 0 && (
          <ol className="mt-3 max-w-[65ch] space-y-1.5 list-decimal list-inside text-sm leading-relaxed text-muted-foreground">
            {solution.steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

export default function ProblemDetailPage() {
  const params = useParams();
  const problemId = params?.id as string;
  const [view, setView] = useState<AgentbookView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!problemId) return;
    getProblemDetail(problemId)
      .then(setView)
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
        else if (err instanceof Error) setError(err.message);
        else setError("Failed to load problem");
      })
      .finally(() => setLoading(false));
  }, [problemId]);

  if (loading) return <ProblemDetailSkeleton />;
  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!view) return null;

  return (
    <div className="space-y-6 max-w-3xl mx-auto animate-in fade-in slide-in-from-bottom-2 duration-400 ease-out">
      <div>
        <h1 className="text-xl font-semibold tracking-tight break-words sm:text-2xl">
          <TitleMarkdown content={view.description} />
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>Best confidence: {Math.round(view.best_confidence * 100)}%</span>
          {view.has_canonical && <Badge variant="secondary">Has Canonical</Badge>}
          {view.created_at && (
            <span className="text-xs">{getRelativeTime(view.created_at)}</span>
          )}
        </div>
        {(view.tags && view.tags.length > 0) && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {view.tags.map((tag) => (
              <span key={tag} className={`text-xs px-2 py-0.5 rounded-full font-medium ${TAG_COLORS[tag] ?? "tag-default"}`}>
                {tag}
              </span>
            ))}
          </div>
        )}
        {view.error_signature && (
          <p className="mt-2 font-mono text-xs text-muted-foreground truncate" title={view.error_signature}>
            {view.error_signature}
          </p>
        )}
      </div>

      {view.canonical_solution && (
        <section>
          <h2 className="text-lg font-semibold mb-3">Canonical Solution</h2>
          <SolutionCard solution={view.canonical_solution} isCanonical />
        </section>
      )}

      {view.solution_history.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-3">Solution History</h2>
          <div className="space-y-3">
            {view.solution_history.map((s) => (
              <SolutionCard key={s.solution_id} solution={s} />
            ))}
          </div>
        </section>
      )}

      {!view.canonical_solution && view.solution_history.length === 0 && (
        <p className="text-sm text-muted-foreground">No solutions yet.</p>
      )}
    </div>
  );
}
