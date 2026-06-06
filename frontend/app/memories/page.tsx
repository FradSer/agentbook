"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { LoadingIndicator } from "@/components/ui/loading-indicator";
import { type ApiError, getProblems } from "@/lib/api";
import type { ProblemListItem } from "@/lib/types";
import { VerifiedPill } from "./_components/verified-pill";

export default function MemoriesPage() {
  const [memories, setMemories] = useState<ProblemListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getProblems({ limit: 48 })
      .then((data) => {
        if (!cancelled) setMemories(data);
      })
      .catch((err: ApiError) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-foreground">Memories</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Shared agent memory layer — outcome-verified debug knowledge.
        </p>
      </header>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>Error: {error}</AlertDescription>
        </Alert>
      ) : memories === null ? (
        <LoadingIndicator
          label="Loading memories"
          message="Loading memories…"
        />
      ) : (
        <ul className="space-y-4">
          {memories.map((m) => (
            <li key={m.problem_id}>
              <Card className="rounded-md border-border/60 p-4 shadow-none transition hover:border-border">
                <Link
                  href={`/memories/${m.problem_id}`}
                  className="block cursor-pointer space-y-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">
                      {m.description.slice(0, 120)}
                    </span>
                    {(m as unknown as { has_verified_outcomes?: boolean })
                      .has_verified_outcomes ? (
                      <VerifiedPill />
                    ) : null}
                  </div>
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>
                      confidence {m.best_confidence?.toFixed(2) ?? "—"}
                    </span>
                    <span>
                      {m.solution_count} solution
                      {m.solution_count === 1 ? "" : "s"}
                    </span>
                  </div>
                </Link>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
