"use client";

import { useEffect, useState } from "react";

type SandboxRun = {
  success: boolean;
  notes: string;
  created_at: string;
};

type ResearchItem = {
  cycle_id: string;
  created_at: string;
  status: string;
  previous_best_confidence: number;
  new_confidence: number;
  reasoning: string;
  sandbox_run: SandboxRun | null;
};

type ResearchResponse = {
  items: ResearchItem[];
  total: number;
  has_more: boolean;
};

export default function ResearchPage() {
  const [items, setItems] = useState<ResearchItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [memoryId, setMemoryId] = useState<string | null>(null);

  useEffect(() => {
    const url = new URL(window.location.href);
    setMemoryId(url.searchParams.get("memory_id"));
  }, []);

  useEffect(() => {
    if (!memoryId) return;
    const base = process.env.NEXT_PUBLIC_API_URL ?? "";
    fetch(`${base}/v1/research-activity?memory_id=${memoryId}&limit=50`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<ResearchResponse>;
      })
      .then((data) => setItems(data.items))
      .catch((err) => setError(String(err)));
  }, [memoryId]);

  if (!memoryId) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-10">
        <h1 className="text-2xl font-semibold">Research</h1>
        <p className="mt-4 text-sm text-muted-foreground">
          Pick a memory from{" "}
          <a href="/memories" className="underline underline-offset-2">
            /memories
          </a>{" "}
          to see its hill-climbing history.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-semibold">Research</h1>
      <p className="mt-1 text-sm text-muted-foreground">Memory: {memoryId}</p>

      {error ? (
        <p className="mt-6 text-sm text-destructive">Error: {error}</p>
      ) : items === null ? (
        <p className="mt-6 text-sm text-muted-foreground">Loading…</p>
      ) : (
        <ol className="mt-8 space-y-4">
          {items.map((item) => {
            const delta = item.new_confidence - item.previous_best_confidence;
            return (
              <li
                key={item.cycle_id}
                className="rounded-md border border-border/60 bg-card p-4"
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-sm font-medium">{item.status}</span>
                  <time className="text-xs text-muted-foreground">
                    {new Date(item.created_at).toLocaleString()}
                  </time>
                </div>
                <p className="mt-2 text-sm text-foreground">
                  confidence {item.previous_best_confidence.toFixed(3)} →{" "}
                  {item.new_confidence.toFixed(3)} ({delta >= 0 ? "+" : ""}
                  {delta.toFixed(3)})
                </p>
                {item.reasoning ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {item.reasoning}
                  </p>
                ) : null}
                {item.sandbox_run ? (
                  <details className="mt-3 rounded border border-border/40 bg-background/40 p-2">
                    <summary className="cursor-pointer text-xs font-medium">
                      Sandbox run — {item.sandbox_run.success ? "pass" : "fail"}
                    </summary>
                    <pre className="mt-2 whitespace-pre-wrap text-xs">
                      {item.sandbox_run.notes}
                    </pre>
                  </details>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}
    </main>
  );
}
