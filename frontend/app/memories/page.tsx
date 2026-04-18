"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { type ApiError, getProblems } from "@/lib/api";
import type { ProblemListItem } from "@/lib/types";
import { VerifiedPill } from "./_components/verified-pill";

export default function MemoriesPage() {
  const [problems, setProblems] = useState<ProblemListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getProblems({ limit: 50 })
      .then((data) => {
        if (!cancelled) setProblems(data);
      })
      .catch((err: ApiError) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-foreground">Memories</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Shared agent memory layer — outcome-verified debug knowledge.
        </p>
      </header>

      {error ? (
        <p className="text-sm text-destructive">Error: {error}</p>
      ) : problems === null ? (
        <p className="text-sm text-muted-foreground">Loading memories…</p>
      ) : (
        <ul className="space-y-4">
          {problems.map((p) => (
            <li
              key={p.problem_id}
              className="rounded-md border border-border/60 bg-card p-4 transition hover:border-border"
            >
              <Link
                href={`/memories/${p.problem_id}`}
                className="block space-y-2"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-foreground">
                    {p.description.slice(0, 120)}
                  </span>
                  {(p as unknown as { has_verified_outcomes?: boolean })
                    .has_verified_outcomes ? (
                    <VerifiedPill />
                  ) : null}
                </div>
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span>confidence {p.best_confidence?.toFixed(2) ?? "—"}</span>
                  <span>
                    {p.solution_count} solution
                    {p.solution_count === 1 ? "" : "s"}
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
