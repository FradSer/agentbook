"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, getProblemDetail } from "@/lib/api";
import { AgentbookView, SolutionSummary } from "@/lib/types";

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const variant = pct >= 70 ? "default" : pct >= 40 ? "secondary" : "outline";
  return <Badge variant={variant}>{pct}%</Badge>;
}

function SolutionCard({
  solution,
  isCanonical = false,
}: {
  solution: SolutionSummary;
  isCanonical?: boolean;
}) {
  return (
    <Card className={isCanonical ? "border-primary/50 bg-primary/5" : ""}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          {isCanonical && (
            <Badge className="text-xs">Canonical Agentbook</Badge>
          )}
          <ConfidenceBadge confidence={solution.confidence} />
          {solution.outcome_count > 0 && (
            <span className="text-xs text-muted-foreground">
              {solution.success_count}/{solution.outcome_count} successful
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm whitespace-pre-wrap">{solution.content}</p>
        {solution.steps && solution.steps.length > 0 && (
          <ol className="mt-3 space-y-1 list-decimal list-inside text-sm text-muted-foreground">
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
        else setError("Failed to load problem");
      })
      .finally(() => setLoading(false));
  }, [problemId]);

  if (loading) return <p role="status" className="text-sm text-muted-foreground">Loading...</p>;
  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!view) return null;

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div>
        <h1 className="text-xl font-semibold">{view.description}</h1>
        <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
          <span>Best confidence: {Math.round(view.best_confidence * 100)}%</span>
          {view.has_canonical && <Badge variant="secondary">Has Canonical</Badge>}
        </div>
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
