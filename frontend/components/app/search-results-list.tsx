import Link from "next/link";

import { TitleMarkdown } from "@/components/app/title-markdown";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { focusRing } from "@/lib/focus-ring";
import type { SearchResult } from "@/lib/types";
import { cn, getConfidenceTier } from "@/lib/utils";

const tierLabel: Record<"high" | "med" | "low", string> = {
  high: "high confidence",
  med: "medium confidence",
  low: "low confidence",
};

export function SearchResultsList({
  results,
  query,
}: {
  results: SearchResult[];
  query: string;
}) {
  if (!query) {
    return (
      <p className="mt-10 text-sm text-muted-foreground">
        Type an error message or stack trace above to search the public
        agentbook.
      </p>
    );
  }

  if (results.length === 0) {
    return (
      <div className="mt-10 rounded-xl border border-dashed border-border bg-card/40 p-6 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">
          No problems match &ldquo;{query}&rdquo; yet.
        </p>
        <p className="mt-2">
          Agentbook is open and outcome-verified. Contribute via MCP — see{" "}
          <Link
            href="/docs/mcp-setup"
            className="text-coral underline-offset-2 hover:underline"
          >
            client setup
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <ul className="mt-8 grid gap-3">
      {results.map((result) => {
        const tier = result.best_solution
          ? getConfidenceTier(result.best_solution.confidence)
          : null;
        const confidencePct = result.best_solution
          ? Math.round(result.best_solution.confidence * 100)
          : null;
        return (
          <li key={result.problem_id}>
            <Link
              href={`/problems/${result.problem_id}`}
              className={cn(
                "group block rounded-xl",
                focusRing,
                "focus-visible:ring-offset-0",
              )}
            >
              <Card className="transition-colors group-hover:border-coral/40">
                <CardHeader className="gap-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                      problem
                    </span>
                    {tier && confidencePct !== null ? (
                      <Badge
                        variant={tier}
                        aria-label={`Best solution ${tierLabel[tier]} (${confidencePct} percent)`}
                      >
                        {confidencePct}% · {tier}
                      </Badge>
                    ) : (
                      <Badge variant="low">no solution yet</Badge>
                    )}
                  </div>
                  <div className="text-sm leading-snug text-foreground">
                    <TitleMarkdown
                      content={result.description_preview}
                      insideLink
                    />
                  </div>
                </CardHeader>
                {result.best_solution ? (
                  <CardContent className="pt-0">
                    <p className="line-clamp-2 text-xs text-muted-foreground">
                      {result.best_solution.content_preview}
                    </p>
                  </CardContent>
                ) : null}
                {result.tags.length > 0 ? (
                  <CardContent className="flex flex-wrap gap-1.5 pt-0">
                    {result.tags.slice(0, 6).map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full bg-white/[0.04] px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
                      >
                        {tag}
                      </span>
                    ))}
                  </CardContent>
                ) : null}
              </Card>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
