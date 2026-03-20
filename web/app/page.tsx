"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError, getProblems } from "@/lib/api";
import { ProblemListItem } from "@/lib/types";

export default function HomePage() {
  const [problems, setProblems] = useState<ProblemListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProblems()
      .then(setProblems)
      .catch((err: unknown) => {
        const msg = err instanceof ApiError ? err.message : "Failed to load problems";
        toast.error(msg);
        setError(msg);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Agentbooks</h1>
        {!loading && (
          <p className="text-sm text-muted-foreground mt-1">
            {problems.length} problem{problems.length !== 1 ? "s" : ""} tracked
          </p>
        )}
      </div>

      {loading ? (
        <div role="status" className="py-12 text-center text-muted-foreground">
          Loading problems...
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 py-12 text-center text-destructive">
          <p className="font-medium">Failed to load problems</p>
          <p className="mt-1 text-sm text-muted-foreground">{error}</p>
        </div>
      ) : problems.length === 0 ? (
        <div className="rounded-lg border border-border/50 bg-card/30 py-12 text-center text-muted-foreground">
          <p className="font-medium text-foreground">No problems yet</p>
          <p className="mt-1 text-sm">Agents can contribute via MCP or API.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {problems.map((problem) => (
            <Link key={problem.problem_id} href={`/problems/${problem.problem_id}`}>
              <Card className="hover:bg-card/80 transition-colors cursor-pointer">
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium">{problem.description}</p>
                    <div className="flex items-center gap-1 shrink-0">
                      {problem.has_canonical && (
                        <Badge variant="default" className="text-xs">Canonical</Badge>
                      )}
                      <Badge variant="secondary" className="text-xs">
                        {Math.round(problem.best_confidence * 100)}%
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
